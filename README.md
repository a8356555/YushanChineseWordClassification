Experimenting on 

https://colab.research.google.com/drive/1_9XwlP7vMmk7C5tZ4Bb-PDSoCeevdOo-#scrollTo=UWss9gCGhiiO

Data info and error handling on 

https://colab.research.google.com/drive/1qeCqtGTHLGT2Ha2H7GdWVqKBElVUCcHG

# Table of Contents
1. [YuShan AI Competition](#yac)
    1. [Environmental info](#ei)
    2. [Usage Note](#un)
    3. [Target](#ta1)
    4. [Dataset info](#di1)
    5. [Experiment](#ex1)
    6. [TODO](#todo1)
2. [(Moved)Noisy Label](#nl)
    1. [Dataset info](#di)
    2. [Target](#ta)
    3. [Papers](#p)
    4. [Experiment](#ex)
    5. [TODO](#todo)
# <a name="yac">1. YuShan AI Competition (Chinese Word Classification)
Test Accuracy 90% so far

## <a name="ei">Environmental info
    Running on Colab:
        Ubuntu 18.04.5 LTS
        Python 3.7.11
        CUDA 11.0
        cudnn 7.6.5
        
    Python pytorch related version:
        torch==1.9.0+cu102
        torchvision==0.10.0+cu102
        
## <a name="un">Usage Note
#### 1. Please check whether you install the following package,        
    pip install pytorch-lightning efficientnet_pytorch cupy-cuda110
    pip install --upgrade --force-reinstall --no-deps albumentations        
    pip install --extra-index-url https://developer.download.nvidia.com/compute/redist --upgrade nvidia-dali-cuda110     
    pip install pytorch-lightning
    pip install cupy-cuda110 "if not using gpu

#### 2. Please Modify data/model/optimizer config in config.py First<br>
* dcfg: data config<br>
* mcfg: model config<br>
* ocfg: optimizer config

#### 3. CLI usage (not tested)
    python3 main.py
        -s --stage train or predict stage
        [-i --input-image /path/to/your/image/to/be/predicted]
        [-m model_type] 
        [-c /path/to/your/own/checkpoint/file ] 
        [-t target metric used for evaluating the best model]

## <a name="ta1">Target
1. Get familiar with Pytorch Lightning.

2. Deploy on flask + gcp using the api provided by the organizer. (App on flask should respond in 1 second)

3. Be Familiar with the following training tricks or tools:
    * Tools: Dali, apex, Pytorch profiler, HDF5,
    * Tricks: different learning rate, learning rate scheduler, gradient check

4. Try to speed up training using the following tricks or tools:
    * Tools: Dali, apex, <br>
    * (Bottleneck) Data loading: HDF5, LMDB, TFRecord, tmpfs, hyperparameters (batch_size + num_threads), data prefetcher (not worked)

5. Try different augmentation using Dali pipeline including custom python numpy function. 

6. Try to fine tune on Resnet / EfficientNet. (Due to the demand of both accuracy and inference speed)

7. Try implement special training tricks such as:
    * Different learning rates, learning rate scheduler, gradient check, hard sample training

## <a name="di1">Dataset Info
1. Around 10~12% error label rate.
2. Too much classes (800 + 1 "isnull")
3. Data imbalance (Most classes have 100 pics, while some have only 20~30 pics)
4. Lack of "other" class image. 
    
## <a name="ex1">Experiment
1. batch_size + num_thread (The bigger one is not the better one)
    * num_thread = 4 or 8 is the fastest (just for this project)

2. dataloader: lmdb vs hdf5 vs dali vs raw loading
    * lmdb: 3s/batch (using the most disk storage and more time to save)
    * hdf5: 2s/batch (using many disk storage, and the save time is large when using high compression level)
    * dali: 3s/batch
    * raw: 4~5s/batch<br>

3. read data: single process vs multi-processing
    * single process: 3m48s / 1000 imgs
    * multi-process: 17s / 1000 imgs
    * Q: why images readed but deleted are still fast to read though not in RAM.

4. read image: pil vs cv2
    * 讀取時PIL比較快，但那是因為PIL只先打開不讀入，若牽扯到之後的操作包含resize，則使用CV2較快

5. model hyperparameter for training
    * num_threads = 4 or 8 is better
    
6. 模型實驗
    * Baseline (resnet18, Adam, lr 1e-3) + 使用 1/3 資料集: ~40% valid accuracy<br>
    * 使用 different learning rate 將模型分為三個部分 (lr = [1e-3, 1e-4, 1e-5]) 進行差分訓練: +10% (~50%)<br>
    * 使用 different learning rate + 1-cycle learning rate scheduler: +2% (~52%)<br>
    * 加入網路上找的其他中文字資料集並且改使用灰階圖片（模型加一層卷積層）來使兩個資料集分布接近 : +6% (~58%)<br>
    * 擴大模型 resnet34: +5% (~63%)<br>
    * 衡量模型需求與資料分布，改使用 efficientnet-b0 與整個原資料集、去除新資料集並加入其他類 (isnull) 來訓練。: +17% (~80%)
    * 增加 data augmentation 使其可以模擬更多新手寫圖片: +10% (~90%)
    * 使用 hard sample training: +?% (~?%)<br><br>
   
* Note    
    * Adam vs SGD: SGD 未能找到超越 Adam 表現的超參數<br>
    * 小資料集時 efficientnet 使用 adam, lr=5e-4 的表現較 lr=1e-3 好，估計是資料太少 lr 太大時將模型參數更新到太歪的地方
    * Learning rate scheduling may be able to make models have better performance, but it requires much time.
    * models using pretrained=False is very hard to train.
    * Normalize image in this project by dividing pixel by 255 is much better than by normalizing using the dataset mean and stddev, why???
    
## <a name="todo1">TODO
1. Use multi-thread to speed up dataloader.

2. Further improve model performance. (test accuracy 90% now)

3. Try to more custom layers.

4. Try to gather more input data. (gather real data or use GAN to generate training images)

5. Try to implement noisy label related skills from papers.

6. Check why images readed but deleted are still fast to read though not in RAM
    
7. Check why normalize image in this project by dividing pixel by 255 is much better than by normalizing using the dataset mean and stddev
    
# <a name="nl">2. Noisy Label
Moved to new repo https://github.com/a8356555/NoisyLabel/blob/main/README.md
    
## <a name="di">Dataset info
* label noise rate around 12%
    
## <a name="ta">Target
* Find an approach effective at finding out errors.
* Find an framework that can build robust models having better performance without manually adjusting the labels.
* Training on hard samples.
    
## <a name="p">Papers
    
## <a name="ex">Experiment
    
## <a name="todo">TODO
* Implementation of approaches of other papers
