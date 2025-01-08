# 라이브러리 및 경로 설정

# Path, natsort, tqdm 등을 사용해 파일 경로를 수집
# cfg 클래스로 데이터셋(브레인 MRI) 위치와 관련 CSV 파일 위치를 한눈에 확인할 수 있게 설계
# 장점: 유지보수 시 경로만 수정해도 전체 코드에 반영 가능
# 데이터 로딩 & DataFrame 구성

# 폴더별로 flair, t1, t1ce, t2, mask NIfTI 파일 경로를 찾고 pandas DataFrame에 저장
# df.dropna()로 누락된 항목이 있는 폴더 제거 → 유효한 이미지 셋만 남김
# 장점: 이미지 경로를 DataFrame으로 관리하면, 추후 메타 정보나 라벨 정보를 쉽게 병합 가능
# 메타데이터 추출

# 각 NIfTI(이미지) 파일에 대해 SimpleITK 또는 nibabel로 로드해 shape, spacing, min/max intensity 확인
# extract_meta_data() 함수로 재사용성 높임
# 장점: 동일한 구조의 메타 정보를 한 번에 모아서, 이미지 특성 분포(예: max intensity)가 어떻게 다른지 파악 용이
# 마스크 라벨 검사

# 각 마스크에서 np.unique()로 0,1,2,4가 맞는지 확인
# BraTS 2020의 표준 라벨(ET=4, ED=2, NCR/NET=1, 배경=0)과 다른 값이 있나 점검
# 장점: 잘못된 라벨링이나 누락된 마스크가 있는지 빠르게 식별 가능
# 값 분포 시각화 (히스토그램)

# meta_df에서 flair_max, t1_max, t1ce_max, t2_max만 골라 sns.histplot으로 분포 확인
# 특정 모달리티(FLAIR, T1CE)는 최대값이 크게 튈 수 있음 → MRI 특성(조영 효과, 수분 함량 등)에 영향
# 장점: 전처리(클리핑, 정규화) 전략 수립에 도움
# 애니메이션 형태의 슬라이스 시각화

# matplotlib.animation.ArtistAnimation 이용
# 3D → 2D 슬라이스를 순회하며 imshow로 표시
# 마스크가 있는 경우 컬러맵(jet) + alpha로 투명도 조절해 겹침
# 장점: 실제 슬라이스 순서대로 tumor 영역 시각적 확인
# MONAI 라이브러리로 통합 로드 & 시각화

# LoadImaged, EnsureChannelFirstd, NormalizeIntensityd 등으로 4채널(MRI 4종) + Label 한 번에 불러옴
# blend_images나 matshow3d를 통해 흑백 영상 + 컬러 라벨로 간단히 오버레이 시각화 가능
# 장점: 의료영상 전처리·증강·학습 파이프라인을 구축하기 편리
# 전반적인 의의

# 데이터셋 구조 파악, 라벨 유효성 검사, 기본 통계(히스토그램), 샘플 시각화(2D/3D) 등 EDA의 핵심이 잘 포함
# 활용 시점: 모델 훈련 전, 데이터 전처리나 증강 설정(정규화 범위, 클리핑 등)을 결정할 때 참고

# 결론적으로, 이 코드는 BraTS 2020 뇌종양 MRI 데이터의 탐색적 분석(EDA)을 위해
# (1) 파일 구조 → DataFrame 변환, (2) 메타 정보 추출, (3) 라벨 검증, (4) 히스토그램 분석, (5) 슬라이스 시각화 같은 단계를 거쳐
# 의미 있는 데이터 인사이트를 얻고 추후 학습에 필요한 전처리 전략을 수립할 수 있도록 도움을 주는 코드입니다.

# -*- coding: utf-8 -*-
"""ch05-05-3d-brain-tumor-segmentation-eda.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1BWygf40czY9c2FkDnP0tmHiE3eMJO0c-
"""

!pip install monai
!pip install natsort

"""# Introduction
* 이번 시간에서는 Brain tumor Semantic segmentation에 대해서 알아보도록 하겠습니다.
* Brain tumor에서는 많은 데이터가 있는데요 그중에서 Challenge data로 잘 알려진 Brats 2020년으로 하도록 하겠습니다.
* Brats 는 꾸준히 Tumor dataset으로 제공되어지며 2023까지 꾸준히 나오고 있습니다.
* 아래의 그림과 같이 데이터의 경우 Multi-Modal의 문제로 Brain의 여러 domain을 한번에 활용하여 접근을 합니다.
* 총 4개의 modal 있음
  * T2 and FLAIR의 경우 tissue water relaxational properties(조직 수분)을 보기에 용이함. (영역이 넓음)
  * T1의 경우 병변의 대한 위치를 나타내며 각기 다른 특징들을 뽑을수 있다.
  * T1Gd 조영제를 투과하여 T1의 영상의 contrast를 올린 영상 , 혈관이 잘 보이는 특징을 가지고 있음.

![스크린샷 2023-12-20 오후 11.10.37.png](https://encrypted-tbn2.gstatic.com/images?q=tbn:ANd9GcSEkPXDpE73fgWvmYNAk7xwRFHW2yXczVl1FoqKwg4b2obIGBvR)

## Why need image processing?
* Brain Tumor중에서 Gliomas라는 종류로서 33%의 비중을 차지합니다.
* 이러한 환자의 진단은 여전히 어렵고 발병시 2년 이하의 생존률을 가지는 위험한 병입니다.
* 하지만 이러한 병변을 판단하는건 가장큰 지름 + 정성적인 평가로만 가능하다 -> 그렇다면 Image processing의역할이 필요함.
* 결국 이러한 방법들은 자동적으로 tumor의 영역을 측정하는데 필요합니다.
* MICCAI 2020년에 solution을 기반한 논문도 출간 되었습니다.

<img src="attachment:7775bd27-5d23-4eb5-95f1-9d3ea0c4149c.png">

## How get annotation?
* 정확한 annotation을 얻기 위해서는 다양한 modal에서 영상의 annotation이 필요합니다.
* 총 3개의 class가 있음.
  * enhancing tumor (ET) : Tumor가 종양으로 커지고 있는 영역 (T1Gd에서 잘보임)
  * non enhancing tumor (NET) & necrotic tumor (NCR) : 종양부분 커지지 않는 영역 (T1Gd & T1에서 잘보임)
  * peritumoral edema (ED): 종양 주위에 발생하는 부종 (FLAIR)에서 잘보임
  * ET/NET/NCR영역을 합하여 tumor core를 만들어냄.
  * 마지막으로 ED를 붙이면 전체 tumor가 완성이 되어짐.
  
  
![스크린샷 2023-12-20 오후 11.10.37.png](https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcS9KS56rk6yjn9g2iRufuJLpfJ1XN0P_0lSMs4VGQZIWhAvmHs6)

* 중앙 : t1에 mask입힌 영상, 빨간색 : ET, 초록색 : NET&NCR, 노락색 : ED
* 왼쪽 위 : T2, 오른쪽 위 : T1, 왼쪽 아래 : T1Gd(contrast enhance), 오른쪽 아래 : FLAIR

# 1. EDA
"""

from pathlib import Path
from natsort import natsorted
from tqdm.notebook import tqdm
from IPython.display import display
from scipy import ndimage

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

class cfg:
    base_path = Path('/kaggle/input/brats20-dataset-training-validation/')
    train_path = base_path/'BraTS2020_TrainingData'/'MICCAI_BraTS2020_TrainingData'
    valid_path = base_path/'BraTS2020_ValidationData'/'MICCAI_BraTS2020_ValidationData' # 사용 X
    train_meta_csv   = train_path/'name_mapping.csv'
    train_survival_csv   = train_path/'survival_info.csv'

    valid_meta_csv   = valid_path/'name_mapping.csv' # 사용 X
    valid_survival_csv   = valid_path/'survival_info.csv' # 사용 X

"""### 1.1 Check & Counting data
* data의 위치 확인 및 갯수 확인은 필요하다.
"""

check_file = lambda x : x if x.is_file() else None
## load all dataset folder
data_dict = {'Brats20ID':[], 'flair':[], 't1':[], 't1ce':[], 't2':[], 'mask':[]}
folder_pathes = natsorted(list(cfg.train_path.glob('*')))

data_dicts = []
for sample_path in tqdm(folder_pathes):
    ## get images and labels
    flair_path = sample_path/str(sample_path.name+'_flair.nii')
    t1_path     = sample_path/str(sample_path.name+'_t1.nii')
    t1ce_path   = sample_path/str(sample_path.name+'_t1ce.nii')
    t2_path     = sample_path/str(sample_path.name+'_t2.nii')
    mask_path   = sample_path/str(sample_path.name+'_seg.nii')

    data_dict['Brats20ID'].append(sample_path.name)
    data_dict['flair'].append(check_file(flair_path))
    data_dict['t1'].append(check_file(t1_path))
    data_dict['t1ce'].append(check_file(t1ce_path))
    data_dict['t2'].append(check_file(t2_path))
    data_dict['mask'].append(check_file(mask_path))

df = pd.DataFrame(data_dict)

# check NAN value
df.isna().sum()
display(df.count())
train = df.dropna().reset_index(drop=True) # 3개 drop (371-368)
display(train.count())

sns.barplot(train.count().to_frame().T)

"""## 1.2 get all meta data
* 모든 데이터의 meta data를 읽어봅시다.
"""

train.head()

"""* 현제 Brats에서 제공해주고 있는 Survival csv도 함께 읽어와서 지금 데이터와 병합을 해봅니다.
-> meta 데이터를 합쳐줌으로써 추후 사용 가능.
"""

train_survival_df = pd.read_csv(cfg.train_survival_csv)
merge_df = train.merge(train_survival_df, how='inner', on='Brats20ID')

"""* nifity파일을 읽어오기 위해서는 다양한 tool이 있습니다.
* 대표적으로 Simple ITK & nibabel이 있는데요
* 이 두개의 라이브러리를 비교해보고 또한 meta data추출까지 진행을 해보록 하겠습니다.
"""

import SimpleITK as sitk # 빠름.
import nibabel as nib

# Commented out IPython magic to ensure Python compatibility.
all_data_path = merge_df[['flair','t1','t1ce','t2']].values # dataframe load하여 동일한 이미지 추출

img = sitk.ReadImage(all_data_path[0][0]) # flair이미지 추가 후 속도 측정
# %time a = sitk.GetArrayFromImage(img)
img = nib.load(all_data_path[0][0])
# %time a = img.get_fdata()

"""* Sitk가 빠른것을 확인이 되었으나 nifity와 itk두개의 라이브러리에서 필수 meta data를 추출해봅시다."""

# https://bo-10000.tistory.com/27

# 둘 다 똑같이 나옴.
## nibabel version
sample_img = nib.load(all_data_path[0][0])

name = all_data_path[0][0].name
sample_header = sample_img.header
img = sample_img.get_fdata()
print(f'file name : {name}')
print(f'image shape : {sample_header.get_data_shape()}')
print(f'Pixel spacing : {sample_header.get_zooms()}')
print(f'Data type : {sample_header.get_data_dtype()}')
print(f'Min, Max value : {np.min(img), np.max(img)}')
print('-------------------------------------------------')
# # ## nibabel version
sample_img = sitk.ReadImage(all_data_path[0][0])
img = sitk.GetArrayFromImage(sample_img)
print(f'image shape : {sample_img.GetSize()}')
print(f'Pixel spacing : {sample_img.GetSpacing()}')
print(f'Data type : {sample_img.GetPixelIDTypeAsString()}')
print(f'Min, Max value :{np.min(img), np.max(img)}')

def extract_meta_data(sample_path, use_itk=True):

    if use_itk:
        sample_img = sitk.ReadImage(sample_path)
        img = sitk.GetArrayFromImage(sample_img)
        return np.min(img), np.max(img), sample_img.GetSize(), sample_img.GetSpacing()
    else:
        sample_img = nib.load(sample_path)
        sample_header = sample_img.header
        img = sample_img.get_fdata()
        return np.min(img), np.max(img), sample_header.get_data_shape(), sample_header.get_zooms()

print(extract_meta_data(all_data_path[0][0]))

meta_dict = {'flair_mima':[],'flair_shape':[],'flair_space':[],
             't1_mima':[],'t1_shape':[],'t1_space':[],
             't1ce_mima':[],'t1ce_shape':[],'t1ce_space':[],
             't2_mima':[],'t2_shape':[],'t2_space':[]}
for multi_modal_path in tqdm(all_data_path): # 각각의 이미지를 읽어 meta data를 dictionary를 만듬.
    flair_path, t1_path, t1ce_path, t2_path = multi_modal_path
    result = [extract_meta_data(i) for i in multi_modal_path]
    flair_meta, t1_meta, t1ce_meta, t2_meta = result

    meta_dict['flair_mima'].append([flair_meta[0],flair_meta[1]])
    meta_dict['flair_shape'].append(flair_meta[2])
    meta_dict['flair_space'].append(flair_meta[3])

    meta_dict['t1_mima'].append([t1_meta[0],t1_meta[1]])
    meta_dict['t1_shape'].append(t1_meta[2])
    meta_dict['t1_space'].append(t1_meta[3])

    meta_dict['t1ce_mima'].append([t1ce_meta[0],t1ce_meta[1]])
    meta_dict['t1ce_shape'].append(t1ce_meta[2])
    meta_dict['t1ce_space'].append(t1ce_meta[3])

    meta_dict['t2_mima'].append([t2_meta[0],t2_meta[1]])
    meta_dict['t2_shape'].append(t2_meta[2])
    meta_dict['t2_space'].append(t2_meta[3])

meta_df = pd.DataFrame(meta_dict) # dict를 df로 만듬.

"""* Check image의 Shape이 맞는지 확인해보며 shape의 형태도 맞는지 체크해본다."""

print(meta_df['flair_space'].unique())
print(meta_df['t1_space'].unique())
print(meta_df['t1ce_space'].unique())
print(meta_df['t2_space'].unique())

print(meta_df['flair_shape'].unique())
print(meta_df['t1_shape'].unique())
print(meta_df['t1ce_shape'].unique())
print(meta_df['t2_shape'].unique())

meta_df['flair_min'] = meta_df['flair_mima'].apply(lambda x : x[0])
meta_df['flair_max'] = meta_df['flair_mima'].apply(lambda x : x[1])

meta_df['t1_min'] = meta_df['t1_mima'].apply(lambda x : x[0])
meta_df['t1_max'] = meta_df['t1_mima'].apply(lambda x : x[1])

meta_df['t1ce_min'] = meta_df['t1ce_mima'].apply(lambda x : x[0])
meta_df['t1ce_max'] = meta_df['t1ce_mima'].apply(lambda x : x[1])

meta_df['t2_min'] = meta_df['t2_mima'].apply(lambda x : x[0])
meta_df['t2_max'] = meta_df['t2_mima'].apply(lambda x : x[1])

meta_df.head() # min, max 값 새 column에 추가.

# 위의 df에서 min, max 값 확인 가능.
melt_df = meta_df.melt(id_vars='flair_mima', value_vars=['flair_max','t1_max','t1ce_max','t2_max'])
sns.histplot(data=melt_df, x='value',hue='variable', kde=True, element="step")
# flair랑 t1ce(contrast enhance)를 보면 튀는 값 있음(밝기 차이 선명) -> max값 분포가 앞에 있음.
# 반면 그냥 t1은 전체적으로 밝기가 어두움.

melt_df = meta_df.melt(id_vars='flair_mima', value_vars=['flair_min','t1_min','t1ce_min','t2_min'])
sns.histplot(data=melt_df, x='value',hue='variable', kde=True, element="step", stat="density")

"""## 1.3 Mask annotation check
* Check all mask has labels
"""

unique_values_per_mask = {
    int(str(path).split('_')[-2] if str(path).split('_')[-2] != '1998.09.19' else '355'): np.unique(
        np.asanyarray(nib.load(str(path)).dataobj)
    ) for path in tqdm(merge_df['mask'].to_list())
}

number_of_incomplete_masks = sum(
    [1 for _, v in unique_values_per_mask.items() if set(v) != set([0,1,2,3])]
)
print(
    f'Number of complete masks: {number_of_incomplete_masks} ({number_of_incomplete_masks / len(unique_values_per_mask) * 100:.2f}%)')

"""## 1.3 Image & mask visulization
* 다른 Notebook에서는 어떻게 image를 visulization을 했는지도 살펴보며 실습을 해보도록 하겠습니다.  
"""

## reference : https://www.kaggle.com/code/mariuszwisniewski/brats2020-eda-and-data-visualization/notebook
from matplotlib import animation, cm, colors, rc
import matplotlib.patches as mpatches

DATA_TYPES = ['flair', 't1', 't1ce', 't2', 'mask']
MASK_LABELS = ['Non-Enhancing Tumor Core',
               'Peritumoral Edema', 'GD-Enhancing Tumor']
MASK_VALUES = [0, 1, 2, 4]
def cmap_discretize(cmap, N):
    """Return a discrete colormap from the continuous colormap cmap.

        cmap: colormap instance, eg. cm.jet.
        N: number of colors.
    """
    if type(cmap) == str:
        cmap = plt.get_cmap(cmap)
    colors_i = np.concatenate((np.linspace(0, 1., N), (0., 0., 0., 0.)))
    colors_rgba = cmap(colors_i)
    indices = np.linspace(0, 1., N+1)
    cdict = {}
    for ki, key in enumerate(('red', 'green', 'blue')):
        cdict[key] = [(indices[i], colors_rgba[i-1, ki],
                       colors_rgba[i, ki]) for i in range(N+1)]
    return colors.LinearSegmentedColormap(cmap.name + "_%d" % N, cdict, 1024)


rc('animation', html='jshtml')


def create_parallel_animation(volumes, case, show_mask=False, alpha=0.6):
    """Create animation of multiple volumes"""
    # transpose volume from (x, y, z) to (z, x, y)
    volumes = np.array([np.transpose(volume, (2, 0, 1)) for volume in volumes])
    fig = plt.figure(figsize=(12, 13))
    fig.tight_layout()
    plt.axis('off')
    plt.suptitle(f'Patient ID: {case}', fontsize=16, fontweight='bold')

    if show_mask: ## mask에 Color를 넣어준다.
        custom_cmap = cmap_discretize(cm.jet, int(np.max(volumes[-1])) + 1)
        normalize = colors.Normalize(vmin=np.min(
            volumes[-1]), vmax=np.max(volumes[-1]))

    axes = []
    for idx, data_type in enumerate(DATA_TYPES[:-1]): # image에 넣을 figure를 만들어준다.
        ax = fig.add_subplot(2, len(DATA_TYPES[:-1]) // 2, idx + 1)
        ax.set_title(data_type.upper(), weight='bold')
        axes.append(ax)

    images = []
    for i, slices in enumerate(zip(*volumes[:-1])): # 한장씩 loop를 돌면서 image를 쌓아준다.
        aux_imgs = []
        for idx, s in enumerate(slices):
            im = axes[idx].imshow(s, animated=True, cmap='bone')
            aux_imgs.append(im)
            if show_mask:
                im2 = axes[idx].imshow(np.ma.masked_where(volumes[-1][i] == 0, volumes[-1][i]),
                                       animated=True, cmap=custom_cmap, alpha=alpha, interpolation='none')
                aux_imgs.append(im2)
        images.append(aux_imgs)

    if show_mask:
        print(np.unique(volumes[-1])[1:])
        patches = [mpatches.Patch(color=custom_cmap(normalize(col_val)),
                                  label=f'{MASK_LABELS[l_idx]}') for l_idx, col_val in enumerate(np.unique(volumes[-1])[1:])]
        plt.legend(handles=patches, loc='upper left', bbox_to_anchor=(0.4, -0.1), borderaxespad=0.4,
                   title='Mask Labels', title_fontsize=18, edgecolor='black', facecolor='#c5c6c7')

    ani = animation.ArtistAnimation(
        fig, images, interval=5000 // len(images), blit=False, repeat_delay=1000
    )
    plt.close()
    return ani

volumes = [nib.load(volume_path).get_fdata() for volume_path in merge_df[DATA_TYPES].loc[0].to_list()]
volumes = [ndimage.rotate(volume, -90, axes=(0,1), reshape=False, order=1) for volume in volumes]

create_parallel_animation(volumes, case='1', show_mask=False)

create_parallel_animation(volumes, case='1', show_mask=True)

"""##

## 1.4 Image & mask visulization
"""

from monai.data import DataLoader, decollate_batch, Dataset
from scipy import ndimage
from monai.transforms import (
    LoadImaged,
    EnsureChannelFirstd,
    Compose,
    NormalizeIntensityd
)
from monai.visualize.utils import (
    blend_images,## label과 Image를 합친 영상
    matshow3d ## 3d image의 visulization
)

data_dicts = []
for images_path, mask_path in zip(merge_df[['flair','t1','t1ce','t2']].values, merge_df['mask'].values):
    data_dicts.append({
            'image':images_path,
            'label':[mask_path]}
            )

train_transform = Compose(
    [
        # load 4 Nifti images and stack them together
    LoadImaged(keys=["image", "label"]),
    EnsureChannelFirstd(keys="image"),
    NormalizeIntensityd(keys="image", nonzero=True, channel_wise=True),
    ])

train_dataset = Dataset(data_dicts, transform=train_transform)

print(f"image shape: {train_dataset[0]['image'].shape}")
print(f"label shape: {train_dataset[0]['label'].shape}")
print(f"pixel spacing: {train_dataset[0]['image'].pixdim}")
for img, title in zip(train_dataset[0]["image"], ['flair','t1','t1ce','t2']):
    _ = matshow3d(
    volume=img[...,50::70],
    fig=None,
    title=title,
    frame_dim=-1,
    show=True,
    cmap="gray",)

train_transform = Compose(
    [
        # load 4 Nifti images and stack them together
    LoadImaged(keys=["image", "label"]),
    EnsureChannelFirstd(keys="image"),
    NormalizeIntensityd(keys="image", nonzero=True, channel_wise=True),
    ])

(train_dataset[0]["label"][None]==1).max()

import matplotlib.pyplot as plt
import torch
for i in range(4):
    if i != 4:
        norm_img = train_dataset[0]["image"][[0]]/train_dataset[0]["image"].max()
        norm_lab = (train_dataset[0]["label"][None]==(i+1))*0.1
        ret = blend_images(image=norm_img, label=norm_lab, alpha=0.5, cmap="hsv", rescale_arrays=False)
        fig,axs = plt.subplots(1,3)
        slice_index = 70
        axs[0].set_title(f"image slice {slice_index}")
        axs[0].imshow(train_dataset[0]["image"][0, :, :, slice_index], cmap="gray")
        axs[1].set_title(f"label slice {slice_index}")
        axs[1].imshow(train_dataset[0]["label"][:, :, slice_index])
        axs[2].set_title(f"blend slice {slice_index}")
        axs[2].imshow(torch.moveaxis(ret[:, :, :, slice_index], 0, -1))

