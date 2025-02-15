import numpy as np
import argparse
import torch
import torchvision
import torch.backends.cudnn as cudnn
import torch.nn.functional as F
import torchvision.datasets as dset
import torchvision.transforms as trn
import torchvision.transforms.functional as trn_F
import torchvision.models as models
import torch.utils.model_zoo as model_zoo
import torch.nn as nn
import re
import os
import sys
# from resnext_50_32x4d import resnext_50_32x4d
# from resnext_101_32x4d import resnext_101_32x4d
# from resnext_101_64x4d import resnext_101_64x4d
from scipy.stats import rankdata
from networks import AttnVGG
from networksinceptionv3 import InceptionV3

if __package__ is None:
    import sys
    from os import path

    sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
    from utils.video_loader import VideoFolder

parser = argparse.ArgumentParser(description='Evaluates robustness of various nets on ImageNet',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
# Architecture
parser.add_argument('--model-name', '-m', default='DenseNet121', type=str,
                    choices=['AttnVGG','InceptionV3','resnet18','alexnet', 'squeezenet1.1', 'vgg11', 'vgg19', 'vggbn',
                             'densenet121', 'densenet169', 'densenet201', 'densenet161',
                             'resnet18', 'resnet34', 'resnet50', 'resnet101', 'resnet152',
                             'resnext50', 'resnext101', 'resnext101_64'])
parser.add_argument('--perturbation', '-p', default='brightness', type=str,
                    choices=['gaussian_noise', 'shot_noise', 'motion_blur', 'zoom_blur',
                             'spatter', 'brightness', 'translate', 'rotate', 'tilt', 'scale',
                             'speckle_noise', 'gaussian_blur', 'snow', 'shear'])
parser.add_argument('--difficulty', '-d', type=int, default=1, choices=[1, 2, 3])
# Acceleration
parser.add_argument('--ngpu', type=int, default=1, help='0 = CPU.')
args = parser.parse_args()
print(args)

# /////////////// Model Setup ///////////////

class DenseNet121(nn.Module):
    """Model modified.

    The architecture of our model is the same as standard DenseNet121
    except the classifier layer which has an additional sigmoid function.

    """
    def __init__(self, out_size):
        super(DenseNet121, self).__init__()
        self.densenet121 = torchvision.models.densenet121(pretrained=True)
        num_ftrs = self.densenet121.classifier.in_features
        self.densenet121.classifier = nn.Sequential(
            nn.Linear(num_ftrs, out_size),
            nn.Sigmoid()
        )

    def forward(self, x):
        x = self.densenet121(x)
        return x

# if args.model_name == 'DenseNet121':
#     net =DenseNet121(14)
#     model_file = '/home/lrh/git/Evaluating_Robustness_Of_Deep_Medical_Models/ChestX-Ray/model_path/model.pth.tar'
#
#     if os.path.isfile(model_file):
#         print("=> loading checkpoint")
#         checkpoint = torch.load(model_file)
#
#         pattern = re.compile(
#             r'^(.*denselayer\d+\.(?:norm|relu|conv))\.((?:[12])\.(?:weight|bias|running_mean|running_var))$')
#         state_dict = checkpoint['state_dict']
#         for key in list(state_dict.keys()):
#             res = pattern.match(key)
#             if res:
#                 new_key = res.group(1) + res.group(2)
#                 state_dict[new_key] = state_dict[key]
#                 del state_dict[key]
#
#         net.load_state_dict(state_dict)
#
#     args.test_bs = 6
#
# if args.model_name == 'InceptionV3':
#     net = InceptionV3(num_classes=4)
# #    model_file = "/home/lrh/git/Evaluating_Robustness_Of_Deep_Medical_Models/Messidor/model_path/messidor_inceptionv3.pkl"
#     model_file = "/home/lrh/store/modelpath/adversarial_defense/Messidor/adversarial_training.pth"
#     net.load_state_dict(torch.load(model_file))
#     net = nn.DataParallel(net).cuda()
#     net.eval()
#     args.test_bs = 6
#
# if args.model_name == 'AttnVGG':
#     net = AttnVGG(num_classes=2, attention=True, normalize_attn=False, vis = False)
#     modelFile = "/home/lrh/store/modelpath/adversarial_defense/Dermothsis/adv_training.pth"
#     checkpoint = torch.load(modelFile)
#     net.load_state_dict(checkpoint['state_dict'])
#     net = nn.DataParallel(net).cuda()
#     net.eval()
#     args.test_bs = 6
#
# if args.model_name == 'alexnet':
#     net = models.AlexNet()
#     net.load_state_dict(model_zoo.load_url('https://download.pytorch.org/models/alexnet-owt-4df8aa71.pth',
#                                            # model_dir='/share/data/lang/users/dan/.torch/models'))
#                                            model_dir='/share/data/vision-greg2/pytorch_models/alexnet'))
#     args.test_bs = 6
#
# elif args.model_name == 'squeezenet1.0':
#     net = models.SqueezeNet(version=1.0)
#     net.load_state_dict(model_zoo.load_url('https://download.pytorch.org/models/squeezenet1_0-a815701f.pth',
#                                            # model_dir='/share/data/lang/users/dan/.torch/models'))
#                                            model_dir='/share/data/vision-greg2/pytorch_models/squeezenet'))
#     args.test_bs = 6
#
# elif args.model_name == 'squeezenet1.1':
#     net = models.SqueezeNet(version=1.1)
#     net.load_state_dict(model_zoo.load_url('https://download.pytorch.org/models/squeezenet1_1-f364aa15.pth',
#                                            # model_dir='/share/data/lang/users/dan/.torch/models'))
#                                            model_dir='/share/data/vision-greg2/pytorch_models/squeezenet'))
#     args.test_bs = 6
#
# elif 'vgg' in args.model_name:
#     if 'bn' not in args.model_name and '11' not in args.model_name:
#         net = models.vgg19()
#         net.load_state_dict(model_zoo.load_url('https://download.pytorch.org/models/vgg19-dcbb9e9d.pth',
#                                                # model_dir='/share/data/lang/users/dan/.torch/models'))
#                                                model_dir='/share/data/vision-greg2/pytorch_models/vgg'))
#     elif '11' in args.model_name:
#         net = models.vgg11()
#         net.load_state_dict(model_zoo.load_url('https://download.pytorch.org/models/vgg11-bbd30ac9.pth',
#                                                # model_dir='/share/data/lang/users/dan/.torch/models'))
#                                                model_dir='/share/data/vision-greg2/pytorch_models/vgg'))
#     else:
#         net = models.vgg19_bn()
#         net.load_state_dict(model_zoo.load_url('https://download.pytorch.org/models/vgg19_bn-c79401a0.pth',
#                                                # model_dir='/share/data/lang/users/dan/.torch/models'))
#                                                model_dir='/share/data/vision-greg2/pytorch_models/vgg'))
#     args.test_bs = 2
#
# elif args.model_name == 'densenet121':
#     net = models.densenet121()
#
#     import re
#     # '.'s are no longer allowed in module names, but pervious _DenseLayer
#     # has keys 'norm.1', 'relu.1', 'conv.1', 'norm.2', 'relu.2', 'conv.2'.
#     # They are also in the checkpoints in model_urls.
#     # This pattern is used to find such keys.
#     pattern = re.compile(
#         r'^(.*denselayer\d+\.(?:norm|relu|conv))\.((?:[12])\.(?:weight|bias|running_mean|running_var))$')
#     state_dict = model_zoo.load_url('https://download.pytorch.org/models/densenet121-a639ec97.pth',
#                                     model_dir='/share/data/vision-greg2/pytorch_models/densenet')
#     for key in list(state_dict.keys()):
#         res = pattern.match(key)
#         if res:
#             new_key = res.group(1) + res.group(2)
#             state_dict[new_key] = state_dict[key]
#             del state_dict[key]
#
#     net.load_state_dict(state_dict)
#     args.test_bs = 5
#
# elif args.model_name == 'densenet161':
#     net = models.densenet161()
#
#     import re
#     pattern = re.compile(
#         r'^(.*denselayer\d+\.(?:norm|relu|conv))\.((?:[12])\.(?:weight|bias|running_mean|running_var))$')
#     state_dict = model_zoo.load_url('https://download.pytorch.org/models/densenet161-8d451a50.pth',
#                                     model_dir='/share/data/vision-greg2/pytorch_models/densenet')
#     for key in list(state_dict.keys()):
#         res = pattern.match(key)
#         if res:
#             new_key = res.group(1) + res.group(2)
#             state_dict[new_key] = state_dict[key]
#             del state_dict[key]
#
#     net.load_state_dict(state_dict)
#
#     args.test_bs = 3
#
# elif args.model_name == 'resnet18':
#     net = models.resnet18()
#     net.load_state_dict(model_zoo.load_url('https://download.pytorch.org/models/resnet18-5c106cde.pth',
#                                            # model_dir='/share/data/lang/users/dan/.torch/models'))
#                                            model_dir='/share/data/vision-greg2/pytorch_models/resnet'))
#     args.test_bs = 5
#
# elif args.model_name == 'resnet34':
#     net = models.resnet34()
#     net.load_state_dict(model_zoo.load_url('https://download.pytorch.org/models/resnet34-333f7ec4.pth',
#                                            # model_dir='/share/data/lang/users/dan/.torch/models'))
#                                            model_dir='/share/data/vision-greg2/pytorch_models/resnet'))
#     args.test_bs = 4
#
# elif args.model_name == 'resnet50':
#     net = models.resnet50()
#     net.load_state_dict(model_zoo.load_url('https://download.pytorch.org/models/resnet50-19c8e357.pth',
#                                            # model_dir='/share/data/lang/users/dan/.torch/models'))
#                                            model_dir='/share/data/vision-greg2/pytorch_models/resnet'))
#     args.test_bs = 4
#
# elif args.model_name == 'resnet101':
#     net = models.resnet101()
#     net.load_state_dict(model_zoo.load_url('https://download.pytorch.org/models/resnet101-5d3b4d8f.pth',
#                                            # model_dir='/share/data/lang/users/dan/.torch/models'))
#                                            model_dir='/share/data/vision-greg2/pytorch_models/resnet'))
#     args.test_bs = 3
#
# elif args.model_name == 'resnet152':
#     net = models.resnet152()
#     net.load_state_dict(model_zoo.load_url('https://download.pytorch.org/models/resnet152-b121ed2d.pth',
#                                            # model_dir='/share/data/lang/users/dan/.torch/models'))
#                                            model_dir='/share/data/vision-greg2/pytorch_models/resnet'))
#     args.test_bs = 3
#
# elif args.model_name == 'resnext50':
#     net = resnext_50_32x4d
#     # net.load_state_dict(torch.load('/share/data/lang/users/dan/.torch/models/resnext_50_32x4d.pth'))
#     net.load_state_dict(torch.load('/share/data/vision-greg2/pytorch_models/resnext_50_32x4d.pth'))
#     args.test_bs = 3
#
# elif args.model_name == 'resnext101':
#     net = resnext_101_32x4d
#     # net.load_state_dict(torch.load('/share/data/lang/users/dan/.torch/models/resnext_101_32x4d.pth'))
#     net.load_state_dict(torch.load('/share/data/vision-greg2/pytorch_models/resnext_101_32x4d.pth'))
#     args.test_bs = 3
#
# elif args.model_name == 'resnext101_64':
#     net = resnext_101_64x4d
#     # net.load_state_dict(torch.load('/share/data/lang/users/dan/.torch/models/resnext_101_64x4d.pth'))
#     net.load_state_dict(torch.load('/share/data/vision-greg2/pytorch_models/resnext_101_64x4d.pth'))
#     args.test_bs = 3
#
# args.prefetch = 4
#
# if args.ngpu > 1:
#     net = torch.nn.DataParallel(net, device_ids=list(range(args.ngpu)))
#
# if args.ngpu > 0:
#     net.cuda()
#
# torch.manual_seed(1)
# np.random.seed(1)
# if args.ngpu > 0:
#     torch.cuda.manual_seed(1)
#
# net.eval()
# cudnn.benchmark = True  # fire on all cylinders

# print("=====>loading pretrained model...")
# clf = InceptionV3(num_classes=4)
# clf = torch.nn.DataParallel(clf)
# cudnn.benchmark = True
# net = clf.cuda()
#
# model_file = "/home/lrh/git/Evaluating_Robustness_Of_Deep_Medical_Models/Messidor/model_path/messidor_inceptionv3.pkl"
# net.load_state_dict(torch.load(model_file))


# CKPT_PATH = '/home/lrh/store/modelpath/adversarial_defense/ChestXay/adversarial_training.pth'
# N_CLASSES = 14
# cudnn.benchmark = True
#     # initialize and load the model
# model = DenseNet121(N_CLASSES).cuda()
# net = torch.nn.DataParallel(model).cuda()
# net.eval()
# if os.path.isfile(CKPT_PATH):
#     print("=> loading checkpoint")
#
# #     modelFile = "/home/lrh/git/libadver/examples/IPIM-AttnModel/models/checkpoint.pth"
# #     checkpoint = torch.load(modelFile)
# #     net.load_state_dict(checkpoint['state_dict'])
#
#     checkpoint = torch.load(CKPT_PATH)
#     net.load_state_dict(checkpoint)
#
#     # pattern = re.compile(
#     #     r'^(.*denselayer\d+\.(?:norm|relu|conv))\.((?:[12])\.(?:weight|bias|running_mean|running_var))$')
#     # state_dict = checkpoint['state_dict']
#     # for key in list(state_dict.keys()):
#     #     res = pattern.match(key)
#     #     if res:
#     #         new_key = res.group(1) + res.group(2)
#     #         state_dict[new_key] = state_dict[key]
#     #         del state_dict[key]
#     #
#     # net.load_state_dict(state_dict)
#     print("=> loaded checkpoint")
# else:
#     print("=> no checkpoint found")
# # print("done")
#
# print('Model Loaded\n')
#
# args.test_bs = 6

print("=====>loading pretrained model...")
clf = InceptionV3(num_classes=4)
net = torch.nn.DataParallel(clf)
cudnn.benchmark = True
net = net.cuda()

model_file = "/home/lrh/store/modelpath/adversarial_defense/Messidor/adversarial_training.pth"
net.load_state_dict(torch.load(model_file))
net.eval()
print("done")
args.test_bs = 6

# /////////////// Data Loader ///////////////
# mean = [0.485, 0.456, 0.406]
# std = [0.229, 0.224, 0.225]
# mean = [0.7012, 0.5517, 0.4875]
# std = [0.0942, 0.1331, 0.1521]

mean = (0.4914, 0.4822, 0.4465)
std = (0.2023, 0.1994, 0.2010)
if args.difficulty > 1 and 'noise' in args.perturbation:
    loader = torch.utils.data.DataLoader(
        VideoFolder(root="/share/data/vision-greg2/users/dan/datasets/ImageNet-P/" +
                         args.perturbation + '_' + str(args.difficulty),
                    transform=trn.Compose([trn.ToTensor(), trn.Normalize(mean, std)])),
        batch_size=args.test_bs, shuffle=False, num_workers=5, pin_memory=True)
else:
    loader = torch.utils.data.DataLoader(
        # VideoFolder(root="/share/data/vision-greg2/users/dan/datasets/ImageNet-P/" + args.perturbation,
        #             transform=trn.Compose([trn.ToTensor(), trn.Normalize(mean, std)])),
        # batch_size=args.test_bs, shuffle=False, num_workers=5, pin_memory=True)
        VideoFolder(root="/home/lrh/dataset/benchmark/chestxray/benchmark_p/" + args.perturbation,
                     transform=trn.Compose([trn.ToTensor(), trn.Normalize(mean, std)])),
        batch_size=args.test_bs, shuffle=False, num_workers=5, pin_memory=True)


print('Data Loaded\n')


# /////////////// Stability Measurements ///////////////

identity = np.asarray(range(1, 1001))
cum_sum_top5 = np.cumsum(np.asarray([0] + [1] * 5 + [0] * (999 - 5)))
recip = 1./identity

# def top5_dist(sigma):
#     result = 0
#     for i in range(1,6):
#         for j in range(min(sigma[i-1], i) + 1, max(sigma[i-1], i) + 1):
#             if 1 <= j - 1 <= 5:
#                 result += 1
#     return result

def dist(sigma, mode='top5'):
    if mode == 'top5':
        return np.sum(np.abs(cum_sum_top5[:5] - cum_sum_top5[sigma-1][:5]))
    elif mode == 'zipf':
        return np.sum(np.abs(recip - recip[sigma-1])*recip)


def ranking_dist(ranks, noise_perturbation=True if 'noise' in args.perturbation else False, mode='top5'):
    result = 0
    step_size = 1 if noise_perturbation else args.difficulty
    print(ranks.shape)

    for vid_ranks in ranks:
        print(vid_ranks.shape)
        result_for_vid = []

        for i in range(step_size):
            perm1 = vid_ranks[i]
            print(perm1.shape)
            perm1_inv = np.argsort(perm1)
            print((vid_ranks[i::step_size][1:]).shape)
            for rank in vid_ranks[i::step_size][1:]:
                perm2 = rank
                print(perm2)
                result_for_vid.append(dist(perm2[perm1_inv], mode))
                if not noise_perturbation:
                    perm1 = perm2
                    perm1_inv = np.argsort(perm1)

        result += np.mean(result_for_vid) / len(ranks)

    return result

# def flip_prob(predictions, noise_perturbation=True if 'noise' in args.perturbation else False):
#     result = 0
#     step_size = 1 if noise_perturbation else args.difficulty
# #    print(step_size)
#
#     for vid_preds in predictions:
#         result_for_vid = []
#
#         a = 0
#         for i in range(step_size):
#             prev_pred = vid_preds[i]
# #            print(prev_pred)
# #            print(vid_preds[i::step_size][1:])
#             for pred in vid_preds[i::step_size][1:]:
# #                print(pred)
#                 for j in range(14):
#                     if prev_pred[j] != pred[j]:
#                         a +=1
# #                result_for_vid.append(int(prev_pred != pred))
# #                if not noise_perturbation: prev_pred = pred
#         result += a / (len(predictions)*14)
#
#     return result
def flip_prob(predictions, noise_perturbation=True if 'noise' in args.perturbation else False):
    result = 0
    step_size = 1 if noise_perturbation else args.difficulty

    for vid_preds in predictions:
        result_for_vid = []

        for i in range(step_size):
            prev_pred = vid_preds[i]

            for pred in vid_preds[i::step_size][1:]:
                result_for_vid.append(int(prev_pred != pred))
                if not noise_perturbation: prev_pred = pred

        result += np.mean(result_for_vid) / len(predictions)

    return result


# /////////////// Get Results ///////////////
#  for multi-label problem
# from tqdm import tqdm
#
# predictions, ranks = [], []
# with torch.no_grad():
#     for data, target in loader:
#         num_vids = data.size(0)
#         data = data.view(-1,3,224,224).cuda()
#         if args.model_name == 'AttnVGG':
#             output,_,_ = net(data)
#         else:
#             output = net(data)
#         for vid in output.view(num_vids, -1, 14):
#             vid = vid > 0.5
#             predictions.append(vid.to('cpu').numpy())

# for single-class
from tqdm import tqdm

predictions, ranks = [], []
with torch.no_grad():
    for data, target in loader:
        num_vids = data.size(0)
#        print(num_vids)
        data = data.view(-1,3,224,224).cuda()
#        print(data.shape)
        if args.model_name == 'AttnVGG':
            output,_,_ = net(data)
        else:
            output = net(data)
            if isinstance(output,tuple):
                output = output[0]



#        print(output.shape)

#         for vid in output.view(num_vids, -1, 2):
# #            print(vid.shape)
#             predictions.append(vid.argmax(1).to('cpu').numpy())
#             ranks.append([np.uint16(rankdata(-frame, method='ordinal')) for frame in vid.to('cpu').numpy()])
#
        for vid in output.view(num_vids, -1, 4):
#            print(vid.shape)
            predictions.append(vid.argmax(1).to('cpu').numpy())
            ranks.append([np.uint16(rankdata(-frame, method='ordinal')) for frame in vid.to('cpu').numpy()])


ranks = np.asarray(ranks)

print('Computing Metrics\n')

print('Flipping Prob\t{:.5f}'.format(flip_prob(predictions)))
#print('Top5 Distance\t{:.5f}'.format(ranking_dist(ranks, mode='top5')))
#print('Zipf Distance\t{:.5f}'.format(ranking_dist(ranks, mode='zipf')))
