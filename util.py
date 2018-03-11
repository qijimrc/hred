import torch
import copy
import pickle
from torch.utils.data import Dataset


def cmp_dialog(d1, d2):
    if len(d1) < len(d2):
        return -1
    elif len(d1) > len(d2):
        return 1
    else:
        return 0


class DialogTurn:
    def __init__(self, item):
        cur_list, i = [], 0
        for d in item:
            cur_list.append(d)
            if d == 2:
                if i == 0:
                    self.u1 = copy.copy(cur_list)
                    cur_list[:] = []
                elif i == 1:
                    self.u2 = copy.copy(cur_list)
                    cur_list[:] = []
                else:
                    self.u3 = copy.copy(cur_list)
                    cur_list[:] = []
                i += 1

    def __len__(self):
        return len(self.u1) + len(self.u2) + len(self.u3)

    def __repr__(self):
        return str(self.u1 + self.u2 + self.u3)


class MovieTriples(Dataset):
    def __init__(self, data_type, length=None):

        if data_type == 'train':
            _file = '/home/harshal/code/research/hred/data/MovieTriples_Dataset/Training.triples.pkl'
        elif data_type == 'valid':
            _file = '/home/harshal/code/research/hred/data/MovieTriples_Dataset/Validation.triples.pkl'
        elif data_type == 'test':
            _file = '/home/harshal/code/research/hred/data/MovieTriples_Dataset/Test.triples.pkl'
        self.utterance_data = []

        with open(_file, 'rb') as fp:
            data = pickle.load(fp)
            for d in data:
                self.utterance_data.append(DialogTurn(d))
        self.utterance_data.sort(cmp=cmp_dialog)
        if length:
            self.utterance_data = self.utterance_data[20000:20000+length]

    def __len__(self):
        return len(self.utterance_data)

    def __getitem__(self, idx):
        dialog = self.utterance_data[idx]
        return dialog, len(dialog.u1), len(dialog.u2), len(dialog.u3)


def tensor_to_sent(x, inv_dict):
    sent = []
    for i in x:
        sent.append(inv_dict[i])

    return " ".join(sent)


# sample a sentence from the test set by using beam search
def inference_beam(dataloader, base_enc, ses_enc, dec, inv_dict, beam=5):
    saved_state = torch.load("enc_mdl.pth")
    base_enc.load_state_dict(saved_state)

    saved_state = torch.load("ses_mdl.pth")
    ses_enc.load_state_dict(saved_state)

    saved_state = torch.load("dec_mdl.pth")
    dec.load_state_dict(saved_state)

    base_enc.eval()
    ses_enc.eval()
    dec.eval()

    for i_batch, sample_batch in enumerate(dataloader):
        u1, u1_lens, u2, u2_lens, u3, u3_lens = sample_batch[0], sample_batch[1], sample_batch[2], sample_batch[3], \
                                                sample_batch[4], sample_batch[5]
        o1, o2 = base_enc(u1, u1_lens), base_enc(u2, u2_lens)
        qu_seq = torch.cat((o1, o2), 1)

        # if we need to decode the intermediate queries we may need the hidden states
        final_session_o = ses_enc(qu_seq)

        # forward(self, ses_encoding, greedy=True, beam=5, x=None, x_lens=None):
        sent = dec(final_session_o, greedy=False)
        # print(tensor_to_sent(sent, inv_dict))
        print(sent)


def calc_valid_loss(data_loader, base_enc, ses_enc, dec):
    base_enc.eval()
    ses_enc.eval()
    dec.eval()

    valid_loss = 0
    for i_batch, sample_batch in enumerate(data_loader):
        u1, u1_lens, u2, u2_lens, u3, u3_lens = sample_batch[0], sample_batch[1], sample_batch[2], sample_batch[3], \
                                                sample_batch[4], sample_batch[5]

        o1, o2 = base_enc(u1, u1_lens), base_enc(u2, u2_lens)
        qu_seq = torch.cat((o1, o2), 1)
        final_session_o = ses_enc(qu_seq)
        loss = dec(final_session_o, u3, u3_lens)
        valid_loss += loss.data[0]

    base_enc.train()
    ses_enc.train()
    dec.train()

    return valid_loss/(1 + i_batch)