# Avatar Image Generator

   Faces Domain <br/>
   <img src="images/Faces_example.jpeg" width="500" />

   Cartoons Domain<br/>
   <img src="images/Cartoons_example.jpeg" width="500" />

   Based on the paper XGAN: https://arxiv.org/abs/1711.05139

## The problem

This repo aims to contribute to the daunting problem of generating a cartoon given the picture of a face.  <br/> <br/>
This is an image-to-image translation problem, which involves many classic computer vision tasks, like style transfer, super-resolution, colorization and semnantic    segmentation. Also, this is a many-to-many mapping, which means that for a given face there are multiple valid cartoons, and for a given cartoon there are multiple valid faces too. </br>

## Datasets

  Faces dataset: we use the VggFace dataset (https://www.robots.ox.ac.uk/~vgg/data/vgg_face/) from the University of Oxford

  Cartoon dataset: we use the CartoonSet dataset from Google (https://google.github.io/cartoonset/), both the versions of 10000 and 100000 items.

## Directory structure

  config.json: contains the model configuration to train/test the model
  weights: contains weights that we save the last time we train the model. The hyperparameters are in config.json

```
├── config.json
├── datasets
│   ├── cartoon_datasets
│   │   ├── cartoonset100k_limited
│   │   │   └── cartoon [15987 entries exceeds filelimit, not opening dir]
│   │   ├── cartoonset100k_limited_df.csv
│   │   ├── cartoonset10k
│   │   │   └── cartoon [10000 entries exceeds filelimit, not opening dir]
│   │   └── cartoonset10k_df.csv
│   ├── face_datasets
│   │   ├── face_images_wo_bg
│   │   │   └── faces [2500 entries exceeds filelimit, not opening dir]
│   │   ├── face_images_wo_bg_permissive
│   │   │   └── faces [2500 entries exceeds filelimit, not opening dir]
│   │   └── vgg_face_dataset
│   │       ├── files [2622 entries exceeds filelimit, not opening dir]
│   │       ├── licence.txt
│   │       └── README
│   └── faces_pucp
│       ├── generated_cartoon_images
│       ├── input_images
│       │   └── data
│       │       ├── danielito.jpeg
│       │       ├── joel_.jpeg
│       │       ├── nigga.jpeg
│       │       └── stev.jpeg
│       └── segmented_images
│           └── data
├── images
│   ├── Cartoons_example.jpeg
│   └── Faces_example.jpeg
├── losses
│   └── __init__.py
├── models
│   └── __init__.py
├── notebooks
│   ├── face_segmentation.ipynb
│   ├── xgan_baseline_david.ipynb
│   ├── xgan_baseline_pytorch_version_2.ipynb
│   ├── xgan_model.ipynb
│   └── xgan_stev.ipynb
├── README.md
├── requirements.txt
├── scripts
│   ├── download_faces.py
│   └── plot_utils.py
├── train.py
├── utils
│   └── __init__.py
└── weights
    └── stev
        └── epoch_300
            ├── c_dann.pth
            ├── d1.pth
            ├── d2.pth
            ├── disc1.pth
            ├── d_shared.pth
            ├── e1.pth
            ├── e2.pth
            └── e_shared.pth
```


## The model

   It is based on the XGAN paper, omitting the Teacher Loss, and adding an autoencoder in the end, trained to learn well only the representation of the cartoons, as to "denoise" the spots and wrong colorisation from the face-to-cartoon outputs of the XGAN.

   The model was trained using hyperparameters that are in config.json. A framework that helped us to find the better hyperparameters was Weights & Biases:

  ```
  wandb login 17d2772d85cbda79162bd975e45fdfbf3bb18911

  ```
  ```
  wandb.init(project="avatar_image_generator")

  ```

  You can see the reporte here: https://wandb.ai/stevramos/avatar_image_generator
