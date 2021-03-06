# running on colab
from google.colab import drive
drive.mount('/content/gdrive')

import os
import random
import numpy as np
import torch
from argparse import ArgumentParser
from train import train
from predict import predict

def seed_torch(seed=1029):
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed) # if you are using multi-GPU.
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.enabled = False
    print('seeded')

def make_parser():
    parser = ArgumentParser(
        description="Usage: python3 main.py -s stage [-i image_path] [-m model_type] [-c checkpoint_path] [-t target_metric]\n if u want to train model please modify config.py first")
    parser.add_argument(
        '--stage', '-s', type=str, default='train', required=True, choices=["train", "predict"]
        help='train or eval stage')
    parser.add_argument(
        '--input-path', '-i', type=str, default='',
        help='/path/to/ur/image/or/image/folder')
    parser.add_argument(
        '--model-type', '-m', type=str, default='effcientnet',
        help='model type use for predicting, eg. efficientnet or noisy_student or resnet')
    parser.add_argument(
        '--checkpoint-path', '-c', type=str, default='',
        help='/path/to/ur/checkpoint/file/path')
    parser.add_argument(
        '--target-metric', '-t', type=str, default='val_loss', choices=["val_loss", "val_acc"]
        help='target metrics used for evaluating the best model')
    
    

    return parser

if __name__ == '__main__':
    seed_torch()
    parser = make_parser()
    args = parser.parse_args()

    if args.stage == "train":        
        model, trainer, data_module = train()
    elif args.stage == "predict":
        predict(args)
