#!/usr/bin/env python
"""
train a convolutional encoder and decoder
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import os
from tqdm.autonotebook import tqdm
from torchvision.utils import save_image

import parts
from dataloaders import *

torch.manual_seed(9001)


class Encoder(nn.Module):

    def __init__(self):
        'define four layers'
        super(Encoder, self).__init__()
        self.conv1 = nn.Conv2d(3, 8, 3, 2)
        self.conv2 = nn.Conv2d(8, 16, 3, 2)
        self.conv3 = nn.Conv2d(16, 32, 3, 2)
        self.conv4 = nn.Conv2d(32, 64, 3, 2)

    def forward(self, x):
        'convolution'
        # output 64, 1, 1
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        x = F.relu(self.conv3(x))
        x = F.relu(self.conv4(x))
        return x


class Decoder(nn.Module):

    def __init__(self):
        'define four layers'
        super(Decoder, self).__init__()
        self.conv4 = nn.ConvTranspose2d(64, 32, 3, 2)
        self.conv3 = nn.ConvTranspose2d(32, 16, 3, 2)
        self.conv2 = nn.ConvTranspose2d(16, 8, 3, 2)
        self.conv1 = nn.ConvTranspose2d(8, 3, 3, 2, output_padding=1)

    def forward(self, x):
        'deconvolution'
        x = F.relu(self.conv4(x))
        x = F.relu(self.conv3(x))
        x = F.relu(self.conv2(x))
        x = torch.tanh(self.conv1(x))
        return x


class SuperEncoder(nn.Module):

    def __init__(self, capacity, normalization_layer_factory):
        super(SuperEncoder, self).__init__()
        self.encoder = torch.nn.Sequential(
            parts.DownDoubleConvolution(capacity, normalization_layer_factory, first_capacity=3),
            parts.DownSampling(capacity, normalization_layer_factory),
            parts.DownDoubleConvolution(2*capacity, normalization_layer_factory),
            parts.DownSampling(2*capacity, normalization_layer_factory),
            parts.DownDoubleConvolution(4 * capacity, normalization_layer_factory),
            parts.DownSampling(4 * capacity, normalization_layer_factory, kernel_size=4),
            parts.DoubleConvolution(8 * capacity, normalization_layer_factory)
        )

    def forward(self, x):
        return self.encoder(x)


class SuperDecoder(nn.Module):

    def __init__(self, capacity, normalization_layer_factory):
        super(SuperDecoder, self).__init__()
        self.decoder = torch.nn.Sequential(
            parts.UpSampling(8 * capacity, normalization_layer_factory, kernel_size=4, output_padding=1),
            parts.UpDoubleConvolution(4 * capacity, normalization_layer_factory),
            parts.UpSampling(4 * capacity, normalization_layer_factory, output_padding=1),
            parts.UpDoubleConvolution(2 * capacity, normalization_layer_factory),
            parts.UpSampling(2 * capacity, normalization_layer_factory, output_padding=1),
            torch.nn.Conv2d(capacity, capacity, 3, 1, padding=1, bias=False),
            torch.nn.ReLU(),
            normalization_layer_factory.create(capacity),
            torch.nn.Conv2d(capacity, 3, 3, 1, padding=1, bias=False),
            torch.nn.Tanh()
        )

    def forward(self, x):
        return self.decoder(x)


class Autoencoder(nn.Module):

    def __init__(self):
        'define encoder and decoder'
        super(Autoencoder, self).__init__()
        self.encoder = Encoder()
        self.decoder = Decoder()
        # normalization_layer = torch.nn.BatchNorm2d
        # self.normalization_layer_factory = parts.NormalizationLayerFactory(normalization_layer)
        # self.encoder = SuperEncoder(32, self.normalization_layer_factory)
        # self.decoder = SuperDecoder(32, self.normalization_layer_factory)

    def forward(self, x):
        'pass through encoder and decoder'
        x = self.encoder(x)
        x = self.decoder(x)
        return x



def train(model, device, train_loader, optimizer, epoch):
    progress = tqdm(enumerate(train_loader), desc="train", total=len(train_loader))
    model.train()
    train_loss = 0
    for i, (data, _) in progress:
        data = data.to(device)
        optimizer.zero_grad()
        output = model(data)
        loss = F.mse_loss(output, data)
        loss.backward()
        optimizer.step()
        train_loss += loss
        progress.set_description("train loss: {:.4f}".format(train_loss/(i+1)))


def test(model, device, test_loader, folder, epoch):
    progress = tqdm(enumerate(test_loader), desc="test", total=len(test_loader))
    model.eval()
    test_loss = 0
    with torch.no_grad():
        for i, (data, _) in progress:
            data = data.to(device)
            output = model(data)
            test_loss += F.mse_loss(output, data)
            # progress.set_description("test loss: {:.4f}".format(test_loss/(i+1)))
            if i == 0:
                output = output.view(100, 3, 32, 32)
                data = data.view(100, 3, 32, 32)
                save_image(output.cpu(), f'{folder}/{epoch}.png', nrow=10)
                save_image(data.cpu(), f'{folder}/baseline{epoch}.png', nrow=10)



def main():
    batch_size = 128
    test_batch_size = 100
    epochs = 20
    save_model = True
    folder = 'convolutional_cifar'

    if not os.path.exists(folder):
        os.makedirs(folder)

    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")
    model = Autoencoder().to(device)
    optimizer = optim.Adam(model.parameters())

    path = 'data'
    train_loader, test_loader = get_cifar10(path, use_cuda, batch_size, test_batch_size)

    for epoch in range(1, epochs + 1):
        train(model, device, train_loader, optimizer, epoch)
        test(model, device, test_loader, folder, epoch)
        print("")
        if save_model:
            torch.save(model.state_dict(), f"{folder}/{epoch}.pt")



if __name__ == '__main__':
    main()
