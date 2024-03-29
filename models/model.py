import torch.nn as nn

from .conformer import Conformer
from .predictors import VarianceAdopter
from .utils import sequence_mask


class ConformerVC(nn.Module):
    def __init__(self, params):
        super(ConformerVC, self).__init__()

        self.in_conv = nn.Conv1d(80, params.encoder.channels, 1)

        self.encoder = Conformer(**params.encoder)
        self.variance_adopter = VarianceAdopter(
            channels=params.encoder.channels,
            dropout=params.encoder.dropout
        )
        self.decoder = Conformer(**params.decoder)

        self.out_conv = nn.Conv1d(params.decoder.channels, 80, 1)

        self.post_net = nn.Sequential(
            nn.Conv1d(80, params.decoder.channels, 5, padding=2),
            nn.BatchNorm1d(params.decoder.channels),
            nn.Tanh(),
            nn.Dropout(0.5),
            nn.Conv1d(params.decoder.channels, params.decoder.channels, 5, padding=2),
            nn.BatchNorm1d(params.decoder.channels),
            nn.Tanh(),
            nn.Dropout(0.5),
            nn.Conv1d(params.decoder.channels, params.decoder.channels, 5, padding=2),
            nn.BatchNorm1d(params.decoder.channels),
            nn.Tanh(),
            nn.Dropout(0.5),
            nn.Conv1d(params.decoder.channels, params.decoder.channels, 5, padding=2),
            nn.BatchNorm1d(params.decoder.channels),
            nn.Tanh(),
            nn.Dropout(0.5),
            nn.Conv1d(params.decoder.channels, 80, 5, padding=2)
        )

    def forward(
        self,
        x,
        x_length,
        y_length,
        pitch,
        tgt_pitch,
        energy,
        tgt_energy,
        path
    ):
        x_mask = sequence_mask(x_length).unsqueeze(1).to(x.dtype)
        y_mask = sequence_mask(y_length).unsqueeze(1).to(x.dtype)
        x = self.in_conv(x) * x_mask
        x = self.encoder(x, x_mask)

        x, (dur_pred, pitch_pred, energy_pred) = self.variance_adopter(
            x,
            x_mask,
            y_mask,
            pitch,
            tgt_pitch,
            energy,
            tgt_energy,
            path,
        )
        x = self.decoder(x, y_mask)
        x = self.out_conv(x)
        x *= y_mask

        x_post = x + self.post_net(x)
        x_post *= y_mask

        return x, x_post, (dur_pred, pitch_pred, energy_pred)

    def infer(self, x, x_length, pitch, energy):
        x_mask = sequence_mask(x_length).unsqueeze(1).to(x.dtype)
        x = self.in_conv(x) * x_mask
        x = self.encoder(x, x_mask)

        x, y_mask = self.variance_adopter.infer(
            x,
            x_mask,
            pitch,
            energy,
        )
        x = self.decoder(x, y_mask)
        x = self.out_conv(x)
        x *= y_mask

        x = x + self.post_net(x)
        x *= y_mask
        return x
