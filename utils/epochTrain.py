import os

import torch
import torch.nn as nn
import torch.nn.functional as F
from tqdm import tqdm
from torch.cuda.amp import autocast
from utils.utils import get_lr


def epochTrain(model_train, model, loss_history, loss, optimizer, epoch, epoch_step, epoch_step_val, gen,
               gen_val,
               endEpoch, Batch_size, scaler, save_period, save_dir, flag):
    # 三元损失
    total_triple_loss = 0
    # 交叉熵损失
    total_CE_loss = 0
    # 准确率
    total_accuracy = 0

    # 验证集的
    val_total_triple_loss = 0
    val_total_CE_loss = 0
    val_total_accuracy = 0

    # 开始训练
    if flag == 0:
        print('Start Train')
        pbar = tqdm(total=epoch_step, desc=f'Epoch {epoch + 1}/{endEpoch}', postfix=dict, mininterval=0.3)
    model_train.train()
    for iteration, batch in enumerate(gen):
        if iteration >= epoch_step:
            break
        images, labels = batch
        with torch.no_grad():
            images = images.cuda(flag)
            labels = labels.cuda(flag)
        # 梯度归零
        optimizer.zero_grad()
        with autocast():
            outputs1, outputs = model_train(images, "train")
            _triplet_loss = loss(outputs1, Batch_size)
            _CE_loss = nn.NLLLoss()(F.log_softmax(outputs, dim=-1), labels)
            _loss = _triplet_loss + _CE_loss
        # 反向传播
        scaler.scale(_loss).backward()
        # 参数优化
        scaler.step(optimizer)
        scaler.update()

        with torch.no_grad():
            accuracy = torch.mean((torch.argmax(F.softmax(outputs, dim=-1), dim=-1) == labels).type(torch.FloatTensor))

        total_triple_loss += _triplet_loss.item()
        total_CE_loss += _CE_loss.item()
        total_accuracy += accuracy.item()

        if flag == 0:
            pbar.set_postfix(**{'triple_loss': total_triple_loss / (iteration + 1),
                                'CE_loss': total_CE_loss / (iteration + 1),
                                'accuracy': total_accuracy / (iteration + 1),
                                'lr': get_lr(optimizer)})
            pbar.update(1)

    # 开始验证
    if flag == 0:
        pbar.close()
        print('Finish Train')
        print('Start Validation')
        pbar = tqdm(total=epoch_step_val, desc=f'Epoch {epoch + 1}/{endEpoch}', postfix=dict, mininterval=0.3)
    model_train.eval()
    for iteration, batch in enumerate(gen_val):
        if iteration >= epoch_step_val:
            break
        images, labels = batch
        # 不进行梯度计算
        with torch.no_grad():
            images = images.cuda(flag)
            labels = labels.cuda(flag)

            optimizer.zero_grad()
            outputs1, outputs = model_train(images, "train")
            _triplet_loss = loss(outputs1, Batch_size)
            _CE_loss = nn.NLLLoss()(F.log_softmax(outputs, dim=-1), labels)
            _loss = _triplet_loss + _CE_loss

            accuracy = torch.mean((torch.argmax(F.softmax(outputs, dim=-1), dim=-1) == labels).type(torch.FloatTensor))
            val_total_triple_loss += _triplet_loss.item()
            val_total_CE_loss += _CE_loss.item()
            val_total_accuracy += accuracy.item()

        if flag == 0:
            pbar.set_postfix(**{'val_triple_loss': val_total_triple_loss / (iteration + 1),
                                'val_CE_loss': val_total_CE_loss / (iteration + 1),
                                'val_accuracy': val_total_accuracy / (iteration + 1),
                                'lr': get_lr(optimizer)})
            pbar.update(1)

    # 记录相关内容
    if flag == 0:
        pbar.close()
        print('Finish Validation')
        loss_history.append_loss(epoch, total_accuracy / epoch_step,
                                 (total_triple_loss + total_CE_loss) / epoch_step,
                                 (val_total_triple_loss + val_total_CE_loss) / epoch_step_val)
        print('Epoch:' + str(epoch + 1) + '/' + str(endEpoch))
        print('Total Loss: %.4f' % ((total_triple_loss + total_CE_loss) / epoch_step))
        if (epoch + 1) % save_period == 0 or epoch + 1 == endEpoch:
            torch.save(model.state_dict(), os.path.join(save_dir, '%03d-l%.3f-vl%.3f.pth' % (
                (epoch + 1), (total_triple_loss + total_CE_loss) / epoch_step,
                (val_total_triple_loss + val_total_CE_loss) / epoch_step_val)))
