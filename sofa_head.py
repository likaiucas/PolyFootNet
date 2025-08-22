import torch 
import torch.nn as nn
from ..builder import HEADS

@HEADS.register_module()
class SOFA(nn.Module):
    def __init__(self, trainable = False,**kwargs):
        super().__init__(**kwargs)
        self.trainable = trainable
        # if trainable:
        self.w = nn.Parameter(torch.ones((1,), requires_grad=True))
        # else: 
        #     self.w = 1
    def x_project_q(self, x):
        # 计算x的长度
        return torch.norm(x, dim=1)
    
    # torch.atan2(x[:, 1], x[:, 0])
    def x_project_k(self, x):
        # 计算x的长度
        l = torch.norm(x, dim=1)
        n_train = len(l)
        l_tile = l.repeat((n_train, 1))
        # keys = l_tile[(1 - torch.eye(n_train)).type(torch.bool)].reshape((n_train, -1))
        return l_tile
    
    def x_project_v(self, x):
        angle = torch.atan2(x[:, 1], x[:, 0])
        n_train = len(angle)
        a_tile = angle.repeat((n_train, 1))
        # values = a_tile[(1 - torch.eye(n_train)).type(torch.bool)].reshape((n_train, -1))
        return a_tile

    def forward(self, x):
        # x = self.xy2al(x)
        # x/=100
        queries = self.x_project_q(x)
        keys = self.x_project_k(x)
        values = self.x_project_v(x)
        # queries和attention_weights的形状为(查询个数，“键－值”对个数)
        queries = queries.repeat_interleave(keys.shape[1]).reshape((-1, keys.shape[1]))
        if self.trainable:
            masking = ((queries - keys)>0)*-1e9
            attention_weights = nn.functional.softmax(masking+((queries - keys) * self.w)**2 / 2, dim=1)
        else:
            # masking = ((keys != keys.max()))*-1e9
            masking = ((keys < keys.mean()+0.1*keys.std()))*-1e9 #+ torch.eye(len(x)).type(torch.bool)
            attention_weights = nn.functional.softmax(masking+((queries - keys))**2 / 2, dim=1)
        
        # values的形状为(查询个数，“键－值”对个数)
        angle = torch.bmm(attention_weights.unsqueeze(1), values.unsqueeze(-1)).reshape(-1)
        length = torch.norm(x, dim=1)
        # angle_ori = torch.atan2(x[:, 1], x[:, 0])
        # angle_ori-angle
        return torch.stack((length * torch.cos(angle), length * torch.sin(angle)), dim=1)#*100
    
@HEADS.register_module()
class SOFA_vector(nn.Module):
    def __init__(self, trainable = False,**kwargs):
        super().__init__(**kwargs)
        self.trainable = trainable
        if trainable:
            self.w = nn.Parameter(0.0452*torch.ones((1,), requires_grad=True))
            self.a = nn.Parameter(1*torch.ones((1,), requires_grad=True))
        else: 
            self.w = 0.0452
            self.a = 1
    def x_project_q(self, x):
        # 计算x的长度
        return torch.norm(x, dim=1)
    
    # torch.atan2(x[:, 1], x[:, 0])
    def x_project_k(self, x):
        # 计算x的长度
        l = torch.norm(x, dim=1)
        n_train = len(l)
        l_tile = l.repeat((n_train, 1))
        # keys = l_tile[(1 - torch.eye(n_train)).type(torch.bool)].reshape((n_train, -1))
        return l_tile
    
    def x_project_v(self, x):
        l = torch.norm(x, dim=1)
        # angle = torch.atan2(x[:, 1], x[:, 0])
        n_train = len(l)

        xx, yy = x[:, 0]/l, x[:, 1]/l
        # a_tile = angle.repeat((n_train, 1))
        # values = a_tile[(1 - torch.eye(n_train)).type(torch.bool)].reshape((n_train, -1))
        return xx.repeat((n_train, 1)), yy.repeat((n_train, 1))

    def forward(self, x):
        # x = self.xy2al(x)
        # x/=100
        queries = self.x_project_q(x)
        keys = self.x_project_k(x)
        values_x, values_y = self.x_project_v(x)
        # queries和attention_weights的形状为(查询个数，“键－值”对个数)
        queries = queries.repeat_interleave(keys.shape[1]).reshape((-1, keys.shape[1]))
        if self.trainable:
            # masking = ((queries - keys)>0)*-1e9
            masking = ((keys < keys.mean()+self.a*keys.std()))*-1e9
            attention_weights = nn.functional.softmax(masking+((queries - keys) * self.w)**2 / 2, dim=1)
        else:
            # masking = ((keys != keys.max()))*-1e9
            masking = ((keys < keys.mean()+self.a*keys.std()))*-1e9
            attention_weights = nn.functional.softmax(masking+((queries - keys) * self.w)**2 / 2, dim=1)
        
        # values的形状为(查询个数，“键－值”对个数)
        xx = torch.bmm(attention_weights.unsqueeze(1), values_x.unsqueeze(-1)).reshape(-1)
        yy = torch.bmm(attention_weights.unsqueeze(1), values_y.unsqueeze(-1)).reshape(-1)
        length = torch.norm(x, dim=1)
        # angle_ori = torch.atan2(x[:, 1], x[:, 0])
        # angle_ori-angle
        x_out = torch.stack((length * xx, length * yy), dim=1)
        return x_out#*100