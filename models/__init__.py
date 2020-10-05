import wandb
import math
import numpy as np
import matplotlib.pyplot as plt
%matplotlib inline
import os, sys

import torch
import torch.nn as nn
import torch.nn.functional as F

import torchvision.transforms as transforms
import torchvision
from torch.autograd import Variable
from torch.utils.data import DataLoader

from tqdm.notebook import tqdm
from PIL import Image

import logging

from keras_segmentation.pretrained import pspnet_50_ADE_20K , pspnet_101_cityscapes, pspnet_101_voc12
import cv2
import helper
import json

class Encoder(nn.Module):
  def __init__(self):
    super(Encoder, self).__init__()
    #c=capacity
    self.conv1 = nn.Conv2d(in_channels=3, out_channels=32, kernel_size=3, stride=2, padding=1, bias=False) # out: 32 x 32 x 32
    self.b1 = nn.BatchNorm2d(32)
    self.conv2 = nn.Conv2d(in_channels=32, out_channels=64, kernel_size=3, stride=2, padding=1, bias=False) #out: 16 x 16 x 64
    self.b2 = nn.BatchNorm2d(64)

  def forward(self, x):
    x = F.relu(self.conv1(x)) #try selu
    x = self.b1(x)
    x = F.relu(self.conv2(x))
    x = self.b2(x)

    return x


class Eshared(nn.Module):
  def __init__(self, dropout_rate=0.5):
    super(Eshared, self).__init__()
    self.conv3 = nn.Conv2d(in_channels=64, out_channels=128, kernel_size=3, stride=2, padding=1, bias=False)
    self.b3 = nn.BatchNorm2d(128)
    self.conv4 = nn.Conv2d(in_channels=128, out_channels=256, kernel_size=3, stride=2, padding=1, bias=False)
    self.b4 = nn.BatchNorm2d(256)
    self.flatten = nn.Flatten()
    self.fc1 = nn.Linear(in_features = 4*4*256, out_features = 1024, bias=False)
    self.bfc1 = nn.BatchNorm1d(1024)
    self.dropout2 = nn.Dropout(dropout_rate)
    self.fc2 = nn.Linear(in_features = 1024, out_features = 1024, bias=False)
    self.bfc2 = nn.BatchNorm1d(1024)

  def forward(self,x):
    x = F.relu(self.conv3(x))
    x = self.b3(x)
    x = F.relu(self.conv4(x))
    x = self.b4(x)
    x = self.flatten(x)
    x = F.relu(self.fc1(x))
    x = self.bfc1(x)
    x = self.dropout2(x)
    x = F.relu(self.fc2(x))
    x = self.bfc2(x)

    return x


class Dshared(nn.Module):
  def __init__(self):
    super(Dshared, self).__init__()
    #c = capacity
    self.deconv1 = nn.ConvTranspose2d(in_channels=1024, out_channels=512, kernel_size=4, stride=2, bias=False)
    self.bd1 = nn.BatchNorm2d(512)
    self.deconv2 = nn.ConvTranspose2d(in_channels=512, out_channels=256, kernel_size=2, stride=2, bias=False)
    self.bd2 = nn.BatchNorm2d(256)

  def forward(self,x):
    x = x.view(-1,1024,1,1)
    x = F.relu(self.deconv1(x))
    x = self.bd1(x)
    x = F.relu(self.deconv2(x))
    x = self.bd2(x)

    return x

class Decoder(nn.Module):
  def __init__(self):
    super(Decoder, self).__init__()
    #c = capacity
    self.deconv3 = nn.ConvTranspose2d(in_channels=256, out_channels=128, kernel_size=2, stride=2, bias=False)
    self.bd3 = nn.BatchNorm2d(128)
    self.deconv4 = nn.ConvTranspose2d(in_channels=128, out_channels=64, kernel_size=2, stride=2, bias=False)
    self.bd4 = nn.BatchNorm2d(64)
    self.deconv5 = nn.ConvTranspose2d(in_channels=64, out_channels=3, kernel_size=2, stride=2)

  def forward(self,x):
    x = F.relu(self.deconv3(x))
    x = self.bd3(x)
    x = F.relu(self.deconv4(x))
    x = self.bd4(x)
    x = torch.tanh(self.deconv5(x))

    return x


class GradReverse(torch.autograd.Function):
  @staticmethod
  def forward(ctx, x):
    return x.view_as(x)

  @staticmethod
  def backward(ctx, grad_output):
    return grad_output.neg() * 0.5


def grad_reverse(x):
  return GradReverse.apply(x)


class Cdann(nn.Module):
  def __init__(self, dropout_rate):
    super(Cdann, self).__init__()
    self.fc1 = nn.Linear(in_features = 1024, out_features = 512)
    self.fc2 = nn.Linear(in_features = 512 , out_features = 256)
    self.dropout2 = nn.Dropout(dropout_rate)
    self.fc3 = nn.Linear(in_features = 256 , out_features = 128)
    self.fc4 = nn.Linear(in_features = 128 , out_features = 64)
    self.dropout4 = nn.Dropout(dropout_rate)
    self.fc5 = nn.Linear(in_features = 64 , out_features = 32)
    self.fc6 = nn.Linear(in_features = 32 , out_features = 16)
    self.dropout6 = nn.Dropout(dropout_rate)
    self.fc7 = nn.Linear(in_features = 16, out_features = 1)

  def forward(self, x):
    x = grad_reverse(x)
    x = F.relu(self.fc1(x))
    x = F.relu(self.fc2(x))
    x = self.dropout2(x)
    x = F.relu(self.fc3(x))
    x = F.relu(self.fc4(x))
    x = self.dropout4(x)
    x = F.relu(self.fc5(x))
    x = F.relu(self.fc6(x))
    x = self.dropout6(x)
    x = torch.sigmoid(self.fc7(x))

    return x

class Discriminator(nn.Module):
  def __init__(self):
    super(Discriminator, self).__init__()
    self.conv1 = nn.Conv2d(in_channels=3, out_channels=16, kernel_size=3, stride=2, padding=1) # out: 32 x 32 x 32
    self.conv2 = nn.Conv2d(in_channels=16, out_channels=32, kernel_size=3, stride=2, padding=1, bias=False) # out: 32 x 32 x 32
    self.b2 = nn.BatchNorm2d(32)
    self.conv3 = nn.Conv2d(in_channels=32, out_channels=32, kernel_size=3, stride=2, padding=1, bias=False) # out: 32 x 32 x 32
    self.b3 = nn.BatchNorm2d(32)
    self.conv4 = nn.Conv2d(in_channels=32, out_channels=32, kernel_size=3, stride=2, padding=1) # out: 32 x 32 x 32
    self.flatten = nn.Flatten()
    self.fc1 = nn.Linear(in_features = 4*4*32, out_features = 1)

  def forward(self, x):
    x = F.leaky_relu(self.conv1(x), 0.2)
    x = F.leaky_relu(self.conv2(x), 0.2)
    x = self.b2(x)
    x = F.leaky_relu(self.conv3(x), 0.2)
    x = self.b3(x)
    x = F.leaky_relu(self.conv4(x), 0.2)
    x = self.flatten(x)
    x = torch.sigmoid(self.fc1(x))

    return x

class Denoiser(nn.Module):
  def __init__(self):
    super(Denoiser, self).__init__()

    self.encoder = nn.Sequential(
        nn.Conv2d(3, 64, kernel_size=3, padding=1),
        nn.ReLU(),
        nn.MaxPool2d(2, 2))

    self.decoder = nn.Sequential(
        nn.Conv2d(64, 64, kernel_size=3, padding=1),
        nn.ReLU(),
        nn.Upsample(scale_factor=2),
        nn.Conv2d(64, 3, kernel_size=3, padding=1))

  def forward(self,x):
    return self.decoder(self.encoder(x))


class Avatar_Generator_Model():
    """
    # Methods
    __init__(dict_model): initializer
    dict_model: layers required to perform face-to-image generation (e1, e_shared, d_shared, d2, denoiser)
    generate(face_image, output_path=None): reutrn cartoon generated from given face image, saves it to output path if given
    load_weights(weights_path): loads weights from given path
    """

    def __init__(self):
        self.e1 = Encoder()
        self.e_shared = Eshared()
        self.d_shared = Dshared()
        self.d2 = Decoder()
        self.denoiser = Denoiser()

    def generate(self, face_image, output_path=None):


        face = self.__extract_face(face_image)
        return self.__to_cartoon(face, output_path)

    def load_weights(self, weights_path='weights/'):
        self.e1.load_state_dict(torch.load(
            weights_path + 'e1.pth'))
        self.e_shared.load_state_dict(
            torch.load(weights_path + 'e_shared.pth'))

        self.d_shared.load_state_dict(
            torch.load(weights_path + 'd_shared.pth'))

        self.d2.load_state_dict(torch.load(
            weights_path + 'd2.pth' ))

        self.denoiser.load_state_dict(
            torch.load(weights_path + 'denoiser.pth'))


    def __extract_face(self, face_image):
        #import model
        # segment image
        # remove background
        # return face
        return face_image

    def __to_cartoon(self, face, output_path):
        self.e1.eval()
        self.e_shared.eval()
        self.d_shared.eval()
        self.d2.eval()
        self.denoiser.eval()


        transform = transforms.Compose(
            [transforms.Resize((64, 64)), transforms.ToTensor()])
        face = transform(face).float()
        X = face.unsqueeze(0)
        with torch.no_grad():
            output = self.e1(X)
            output = self.e_shared(output)
            output = self.d_shared(output)
            output = self.d2(output)
            output = self.denoiser(output)
        if output_path is not None:
            # save to path
            # fileName.jpg part of output_path
            torchvision.utils.save_image(tensor=output, fp=output_path)
        return torchvision.transforms.ToPILImage()(output[0])
