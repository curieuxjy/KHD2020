import os
import cv2
import random
from collections import defaultdict
import numpy as np
from imgaug import augmenters as iaa
from sklearn.model_selection import train_test_split

from utils.transform import ImagePreprocessing

import torch
from torch.utils.data import Dataset, DataLoader, TensorDataset

from nsml.constants import DATASET_PATH

def DataLoad(imdir, args):
    impath = [os.path.join(dirpath, f) for dirpath, dirnames, files in os.walk(imdir) for f in files if all(s in f for s in ['.jpg'])]

    img_list = defaultdict(list)
    print('Loading', len(impath), 'images ...')

    for i, p in enumerate(impath):
        img_whole = cv2.imread(p, 0)
        h, w = img_whole.shape
        h_, w_ = h, w//2
        l_img = img_whole[:, w_:2*w_]
        r_img = img_whole[:, :w_]

        _, l_cls, r_cls = os.path.basename(p).split('.')[0].split('_')

        if l_cls=='0' or l_cls=='1' or l_cls=='2' or l_cls=='3':
            img_list[int(l_cls)].append(l_img)
        if r_cls=='0' or r_cls=='1' or r_cls=='2' or r_cls=='3':
            img_list[int(r_cls)].append(r_img)

    img_train,img_val = [],[]
    lb_train,lb_val = [],[]

    if args.num_classes==4 and args.balancing_method=='aug':
        for i in [1,0,2,3]:
            timg, vimg, tlabel, vlabel = train_test_split(img_list[i],[i]*len(img_list[i]),test_size=0.2,shuffle=True,random_state=13241)

            if i == 1:
                num = len(timg)
            if i == 0:
                # downsample class 0, upsample class 2,3
                timg = random.sample(timg, num)
                tlabel = [0] * num
            if i == 2 or i == 3:
                class_remain = (num - len(timg)) % len(timg)
                class_quot = int((num - len(timg)) / len(timg))
                timg += timg * class_quot
                timg += random.sample(timg, class_remain)
                tlabel = [i] * num

            timg_flip = [cv2.flip(img, 1) for img in timg]
            timg += timg_flip
            tlabel = tlabel * 2
            print("train class",i,len(timg))
            img_train += timg
            img_val += vimg
            lb_train += tlabel
            lb_val += vlabel
    
    elif args.num_classes==2 or args.balancing_method=='weights':
        for i in range(4):
            timg, vimg, tlabel, vlabel = train_test_split(img_list[i],[i]*len(img_list[i]),test_size=0.2,shuffle=True,random_state=13241)
            timg_flip = [cv2.flip(img, 1) for img in timg]
            timg += timg_flip
            tlabel = tlabel * 2
            print("train class",i,len(timg))
            img_train += timg
            img_val += vimg
            lb_train += tlabel
            lb_val += vlabel

    print(len(img_train), 'Train data with label 0-3 loaded!')
    print(len(img_val), 'Validation data with label 0-3 loaded!')

    return img_train, lb_train, img_val, lb_val


class Sdataset(Dataset):
    def __init__(self, images, labels, args, augmentation):
        self.images = images
        self.args = args
        self._init_images()
        self.labels = labels
        self.augmentation = augmentation

        print("images:", len((self.images)), "#labels:", len((self.labels)))

    def _init_images(self):
        self.images = ImagePreprocessing(self.images, self.args)
        self.images = np.array(self.images)
        self.images = np.expand_dims(self.images, axis=1)

    def augment_img(self, img):
        scale_factor = random.uniform(1-self.args.scale_factor, 1+self.args.scale_factor)
        rot_factor = random.uniform(-self.args.rot_factor, self.args.rot_factor)

        seq = iaa.Sequential([
                iaa.Affine(
                    scale=(scale_factor, scale_factor),
                    rotate=rot_factor
                )
            ])

        seq_det = seq.to_deterministic()
        img = seq_det.augment_images(img)

        return img

    def __getitem__(self, index):
        image = self.images[index]
        label = self.labels[index]

        if self.augmentation:
            image = self.augment_img(image)

        image = torch.tensor(image).float()

        if self.args.num_classes==2:
            label = 1 if label > 0 else 0

        return image, label

    def __len__(self):
        return len(self.labels)


def load_dataloader(args):
    timages, tlabels, vimages, vlabels = DataLoad(imdir=os.path.join(DATASET_PATH, 'train'), args=args)
    tr_set = Sdataset(timages, tlabels, args, True)
    val_set = Sdataset(vimages, vlabels, args, False)
    batch_train = DataLoader(tr_set, batch_size=args.batch_size, shuffle=True)
    batch_val = DataLoader(val_set, batch_size=args.batch_size, shuffle=False)

    return batch_train, batch_val