# dataset.py
import re
from torch.utils.data import Dataset, DataLoader, random_split

import pytorch_lightning as pl
from nvidia.dali.pipeline import Pipeline
import nvidia.dali.fn as fn
import nvidia.dali.types as types
import nvidia.dali.ops as ops
import nvidia.dali.plugin.pytorch as dalitorch
from nvidia.dali.plugin.pytorch import DALIClassificationIterator, DALIGenericIterator
from nvidia.dali.plugin.base_iterator import LastBatchPolicy

from .preprocess import transform_func, second_source_transform_func, dali_custom_func, dali_warpaffine_transform
from .utils import ImageReader, NoisyStudentDataHandler
from .config import DCFG, MCFG, NS

# TODO: decouple gray, add dali augmentation
#
class BasicDataset(Dataset):
    """Parent Class for all Dataset
    Init Arguments:
        inp_dict: dict, with key value pair {'label': labels, 'image', images, ...}
        transform: function
    """
    def __init__(self, inp_dict, transform=None):
        self.labels = inp_dict['label']
        self.images = inp_dict['image']
        self.image_paths = inp_dict['path']
        self.transform = transform

    def __len__(self):
        return len(self.image_paths)
        
    def __getitem__(self, index):
        if self.images:
            image = self.images[index]
        else:
            path = self.image_paths[index]
            image = ImageReader.read_image_cv2(path)
        
        label = int(self.labels[index])
        
        if self.transform:            
            transformed_image = self.transform(image=image)

        return transformed_image, label

class CustomDataset(BasicDataset):
    pass


class YuShanDataset(Dataset):
    def __init__(self, inp_dict, transform=None): 
        super().__init__(inp_dict, transform)    
        self.labels = inp_dict['int_label']        


class YushanDataModule(pl.LightningDataModule):
    def __init__(self, train_dataset, valid_dataset):
        super().__init__()
        self.train = train_dataset
        self.valid = valid_dataset

    def train_dataloader(self):
        return DataLoader(self.train, batch_size=DCFG.batch_size, num_workers=DCFG.num_workers, pin_memory=DCFG.is_memory_pinned, shuffle=DCFG.is_shuffle)
        
    def val_dataloader(self):
        return DataLoader(self.valid, batch_size=DCFG.batch_size, num_workers=DCFG.num_workers, pin_memory=DCFG.is_memory_pinned)        



# ------------------
# DALI
# ------------------
class BasicPipeline(Pipeline):
    def __init__(self, 
            inp_dict, 
            batch_size=DCFG.batch_size, 
            num_workers=DCFG.num_workers, 
            phase='train', 
            device_id=0,
            exec_async=True, 
            exec_pipelined=True, 
            seed=42
        ):
        super().__init__(batch_size, num_workers, device_id, exec_async=exec_async, exec_pipelined=exec_pipelined, seed=seed)
        random_shuffle = True if phase == 'train' else False
        self.input = ops.readers.File(files=inp_dict['path'], labels=inp_dict['int_label'], random_shuffle=random_shuffle, name="Reader")
        self.decode = ops.decoders.Image(device="mixed", output_type=types.RGB)
        self.dali_device = 'gpu'
        self.resize = ops.Resize(device=self.dali_device)
        self.crop = ops.Crop(device=self.dali_device, crop=[224.0, 224.0], dtype=types.FLOAT)
        self.transpose = ops.Transpose(device=self.dali_device, perm=[2, 0, 1])
        self.phase = phase
    
    def define_graph(self):
        pass

class BasicCustomPipeline(BasicPipeline):
    def __init__(self, 
            inp_dict,
            custom_func=None,
            batch_size=DCFG.batch_size, 
            num_workers=DCFG.num_workers, 
            phase='train', 
            device_id=0
        ):
        super().__init__(
            inp_dict, 
            batch_size, 
            num_workers, 
            phase, 
            device_id, 
            exec_async=False,
            exec_pipelined=False, 
            seed=42
            )
        self.custom_func = custom_func


    def define_graph(self):
        self.jpegs, self.labels = self.input() 
        output = self.decode(self.jpegs)
        if self.custom_func:
            output = fn.python_function(output, function=self.custom_func)
        output = self.resize(output, size=(248.0, 248.0))
        output = self.crop(output)
        output = self.transpose(output)
        output = output/255.0
        return (output, self.labels)

class AddRotatePipeline(BasicCustomPipeline):
    def __init__(self, 
            inp_dict,
            custom_func=None,  
            batch_size=DCFG.batch_size, 
            num_workers=DCFG.num_workers, 
            phase='train', 
            device_id=0
        ):        
        super().__init__(inp_dict, custom_function, batch_size, num_workers, phase, device_id)
        self.rotate = ops.Rotate(device=self.dali_device)  

    def define_graph(self):
        angle = fn.random.uniform(values=[0]*8 + [90.0, -90.0]) # 20% change rotate
        self.jpegs, self.labels = self.input() # (name='r')
        output = self.decode(self.jpegs)
        if self.custom_func:
            output = fn.python_function(output, function=self.custom_func)
        w = fn.random.uniform(range=(224.0, 320.0))
        h = fn.random.uniform(range=(224.0, 320.0))        
        output = self.resize(output, resize_x=w, resize_y=h)                
        output = self.crop(output)        
        output = self.rotate(output, angle=angle)
        if 'gray' in DCFG.transform_approach:
            output = fn.color_space_conversion(Types.RGB, Types.GRAY)
        output = self.transpose(output)
        output = output/255.0
        return (output, self.labels)

class AddWaterPipeline(BasicCustomPipeline):
    def __init__(self, 
            inp_dict, 
            custom_func=None, 
            batch_size=DCFG.batch_size, 
            num_workers=DCFG.num_workers, 
            phase='train', 
            device_id=0
        ):        
        super().__init__(inp_dict, custom_func, batch_size, num_workers, phase, device_id)
        self.water = ops.Water(device=self.dali_device)  

    def define_graph(self):
        angle = fn.random.uniform(values=[0]*8 + [90.0, -90.0]) # 20% change rotate
        self.jpegs, self.labels = self.input() # (name='r')
        output = self.decode(self.jpegs)
        if self.custom_func:
            output = fn.python_function(output, function=self.custom_func)
        w = fn.random.uniform(range=(224.0, 320.0))
        h = fn.random.uniform(range=(224.0, 320.0))        
        output = self.resize(output, resize_x=w, resize_y=h)        
        output = self.crop(output)        
        output = self.water(output)
        output = self.transpose(output)
        output = output/255.0
        return (output, self.labels) 


class NoisyStudentPipeline(BasicCustomPipeline):
    def __init__(self, 
            inp_dict,
            custom_func=None,
            warpaffine_transform=None,
            batch_size=DCFG.batch_size, 
            num_workers=DCFG.num_workers, 
            phase='train', 
            device_id=0
        ):        
        super().__init__(inp_dict, custom_func, batch_size, num_workers, phase, device_id)
        self.rotate = ops.Rotate(device=self.dali_device)  
        self.gaussian_blur = ops.GaussianBlur(device=self.dali_device, window_size=5)
        self.twist = ops.ColorTwist(device=self.dali_device)
        self.jitter = ops.Jitter(device=self.dali_device)
        self.warpaffine_transform = warpaffine_transform
        self.warpaffine = ops.WarpAffine(device=self.dali_device)

    def define_graph(self):
        angle = fn.random.uniform(values=[0]*8 + [90.0, -90.0]) # 20% change rotate
        self.jpegs, self.labels = self.input() # (name='r')
        output = self.decode(self.jpegs)
        if self.custom_func:
            output = fn.python_function(output, function=self.custom_func)
        
        raw_output = self.resize(output, resize_x=248, resize_y=248)
        raw_output = self.crop(raw_output)
        raw_output = self.transpose(raw_output)
        raw_output = raw_output/255.0

        w = fn.random.uniform(range=(224.0, 320.0))
        h = fn.random.uniform(range=(224.0, 320.0))        
        output = self.resize(output, resize_x=w, resize_y=h)
        output = self.crop(output)        
        output = self.rotate(output, angle=angle)
        output = self.gaussian_blur(output)
        s = fn.random.uniform(range=(0.5, 1.5)) 
        c = fn.random.uniform(range=(0.5, 1.5))  
        b = fn.random.uniform(range=(0.875, 1.125)) 
        h = fn.random.uniform(range=(-0.5, 0.5))
        output = self.twist(output, saturation=s, contrast=c, brightness=b, hue=h)
        output = self.jitter(output)
        p =  fn.random.uniform(range=(-0.5, 0.5))
        if self.warpaffine_transform:
            transform = fn.external_source(batch=False, source=self.warpaffine_transform)
            output = self.warpaffine(output, matrix=transform)
        output = self.transpose(output)
        output = output/255.0
        return (raw_output, output, self.labels)

class DaliModule(pl.LightningDataModule):
    def __init__(self, train_pipeline, valid_pipeline):
        super().__init__()
        self.pip_train = train_pipeline
        self.pip_train.build()
        self.pip_valid = valid_pipeline
        self.pip_valid.build()
        self.train_loader = DALIGenericIterator(self.pip_train, ["raw_data", "aug_data", "label"] ,reader_name="Reader", last_batch_policy=LastBatchPolicy.PARTIAL, auto_reset=True)
        self.valid_loader = DALIGenericIterator(self.pip_valid, ["data", "label"], reader_name="Reader", last_batch_policy=LastBatchPolicy.PARTIAL, auto_reset=True)
    def train_dataloader(self):
        return self.train_loader
        
    def val_dataloader(self):
        return self.valid_loader

def get_input_data_and_transform_func(data_type=DCFG.data_type):
    """
    Arguments:
        data_type: str, 'mixed' or 'cleaned' or '2nd' or 'noisy_student'
    """        
    train_images ,valid_images, train_labels, valid_labels = None, None, None, None
    train_image_paths, valid_image_paths, train_int_labels, valid_int_labels = None, None, None, None
    
    transform_function = transform_func
    if data_type == 'noisy_student':
        ( noised_image_paths, noised_int_labels,
        cleaned_image_paths, cleaned_int_labels,
        valid_image_paths, valid_int_labels) = NoisyStudentDataHandler.get_noisy_student_data(student_iter=NS.student_iter)
        train_image_paths = noised_image_paths + cleaned_image_paths
    
    else:
        if data_type == 'mixed':
            method_name = 'get_paths_and_int_labels'
            kwargs = {'train_type': 'mixed'}
                    
        elif data_type == 'cleaned':
            method_name = 'get_paths_and_int_labels'
            kwargs = {'train_type': 'cleaned'}
            
        elif data_type == '2nd':
            method_name = 'get_second_source_data' 
            kwargs = {}               
            transform_function = second_source_transform_func        

        train_image_paths, valid_image_paths, train_int_labels, valid_int_labels = getattr(FileHandler, method_name)(**kwargs)
        valid_images = ImageReader.get_image_data_mp(valid_image_paths, target="image")
    
    print(f"data type: {data_type}, train data numbers: {len(train_image_paths)}, valid data numbers: {len(valid_image_paths)}")
    train_input_dict = {'image': train_images, 'label': train_labels, 'path': train_image_paths, 'int_label': train_int_labels}
    valid_input_dict = {'image': valid_images, 'label': valid_labels, 'path': valid_image_paths, 'int_label': valid_int_labels}
    return train_input_dict, valid_input_dict, transform_function

def get_datasets(
        train_input_dict, 
        valid_input_dict,
        transform_func=None, 
        is_dali_used=DCFG.is_dali_used, 
        data_type=DCFG.data_type,
        **kwargs
    ):
    """
    kwargs:
        dali_custom_func: Optional
        dali_warpaffine_transform: Optional
    """
    
    dali_custom_func,  dali_warpaffine_transform = None, None    
    if "dali_custom_func" in kwargs.keys():
        dali_custom_func = kwargs["dali_custom_func"]
    
    if "dali_warpaffine_transform" in kwargs.keys():
        dali_warpaffine_transform = kwargs["dali_warpaffine_transform"]
    
    if data_type == 'noisy_student':    
        train_dataset = NoisyStudentPipeline(train_input_dict, custom_func=dali_custom_func, warpaffine_transform=dali_warpaffine_transform)
        valid_dataset = BasicCustomPipeline(valid_input_dict, custom_func=dali_custom_func, phase="valid")
    elif is_dali_used:
        train_dataset = AddRotatePipeline(train_input_dict, custom_func=dali_custom_func)
        valid_dataset = BasicCustomPipeline(valid_input_dict, custom_func=dali_custom_func, phase="valid")
    elif data_type == "mixed" or "cleaned" or "2nd":
        train_dataset = YuShanDataset(train_input_dict, transform_func=transform_func)
        valid_dataset = YuShanDataset(valid_input_dict, transform_func=transform_func, phase="valid")    
    else:
        raise ValueError("Invalid input, please check")
        
    return train_dataset, valid_dataset

def get_datamodule(train_dataset, valid_dataset, is_dali_used=DCFG.is_dali_used):
    if is_dali_used:
        return DaliModule(train_dataset, valid_dataset)
    else:
        return YushanDataModule(train_dataset, valid_dataset)

def create_datamodule(is_dali_used=DCFG.is_dali_used, data_type=DCFG.data_type):
    train_input_dict, valid_input_dict, transform_func = get_input_data_and_transform_func(data_type)
    kwargs = {"dali_custom_func": dali_custom_func, "dali_warpaffine_transform": dali_warpaffine_transform}
    train_dataset, valid_dataset = get_datasets(
        train_input_dict, 
        valid_input_dict,
        transform_func, 
        is_dali_used=is_dali_used,
        data_type=data_type,
        **kwargs
        ) 

    datamodule = get_datamodule(train_dataset, valid_dataset, is_dali_used=is_dali_used)    
    print(f"Using dali: {is_dali_used}, module type: {datamodule.__class__}")
    return datamodule