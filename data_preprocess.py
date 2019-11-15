# coding: utf-8
import pickle
import re

import numpy as np
import pyltp
import thulac
import torch
from torch.nn.utils.rnn import pack_sequence

corups_file = ['data/LabeledData.{}.txt'.format(i) for i in range(1, 6)]
word2vec_file = 'model/word2vec.pkl'
save = 'data/train_data.pkl'

# one-hot embedding of POS tag
id2pos = ['x']
pos2id = {'x': 0}
def id_of_pos(pos):
    if pos not in id2pos:
        id2pos.append(pos)
        pos2id[pos] = id2pos.index(pos)
    return pos2id[pos]

# four types of relations
id2relation = ['I', 'B', 'E', 'P']
relation2id = {}
for i, r in enumerate(id2relation):
    relation2id[r] = i


# get the word2vec embedding of a word
print('loading pretrained word2vec model...')
# word2vec = KeyedVectors.load_word2vec_format(embedding_file, binary=False)
with open(word2vec_file, 'rb') as f:
    word2vec = pickle.load(f)
print('finish loading')
unknown = np.ones(word2vec.vector_size, dtype=np.float32)
def embedding(word):
    if word in word2vec:
        return word2vec[word]
    else:
        em = np.zeros(word2vec.vector_size, dtype=np.float32)
        for c in word:
            if c in word2vec:
                em = em + word2vec[c]
            else:
                em = em + unknown
        return em

# segment words in the sentence with the help of given named entity
segmentor = thulac.thulac()
def segment(sent):
    words = []
    postags = []
    segments = re.split('{([^}]*/n.)}', sent)
    for seg in segments:
        m = re.match('(.*)/(n.)', seg)
        if m:
            words.append(m.group(1))
            postag = m.group(2)
            # thulac use 'np' to represent people
            if postag == 'nr':
                postag = 'np'
            postags.append(id_of_pos(postag))
        else:
            s = segmentor.fast_cut(seg)
            words.extend(x[0] for x in s)
            postags.extend(id_of_pos(x[1]) for x in s)
    return (words, postags)


# process samples from dataset
words_samples = [] # for debug
embedding_samples = []
postag_samples = []
position1_samples = []
position2_samples = []
labels = []
max_length = 120
for filename in corups_file:
    print('processing "{}"'.format(filename))

    with open(filename, encoding='utf-8') as f:
        new_sample = True
        sents = []
        for line in f.readlines():
            line = line.strip()

            # end of the sample
            if line == '':
                new_sample = True
                continue

            # new sample
            if new_sample:
                sents = pyltp.SentenceSplitter.split(line)
                new_sample = False
                continue

            # relation labels
            relation = line.split('|')
            # some entity may have several names
            # and some marked entity may not appear in the sentence
            for sent in sents:
                words, postags = segment(sent)
                # l = max_length - len(words)
                embeddings = torch.tensor([embedding(w) for w in words])
                postags = torch.tensor(postags)
                # embeddings.extend([unknown] * l)
                # postags.extend([pos2id['x']] * l)
                for ne1 in relation[0].split(','):
                    if ne1 not in words:
                        continue
                    for ne2 in relation[1].split(','):
                        if ne2 not in words:
                            continue
                        words_samples.append(words)
                        embedding_samples.append(embeddings)
                        postag_samples.append(postags)
                        labels.append(relation2id[relation[2]])

                        i1 = words.index(ne1)
                        i2 = words.index(ne2)
                        positions1 = torch.abs(torch.tensor(range(-i1, len(words) - i1)))
                        positions2 = torch.abs(torch.tensor(range(-i2, len(words) - i2)))
                        position1_samples.append(positions1)
                        position2_samples.append(positions2)
                        # position1_samples.append(list(range(-i1, max_length - i1)))
                        # position2_samples.append(list(range(-i2, max_length - i2)))
num_instance = len(embedding_samples)
print('total', len(embedding_samples), 'instances')


embedding_samples = pack_sequence(embedding_samples, enforce_sorted=False)
postag_samples    = pack_sequence(postag_samples, enforce_sorted=False)
position1_samples = pack_sequence(position1_samples, enforce_sorted=False)
position2_samples = pack_sequence(position2_samples, enforce_sorted=False)
# embedding_samples = np.asarray(embedding_samples)
# postag_samples = np.asarray(postag_samples)
# position1_samples = np.asarray(position1_samples)
# position2_samples = np.asarray(position2_samples)
labels = torch.tensor(labels)

# save
config = {}
config['EMBEDDING_LENGTH'] = word2vec.vector_size
config['RELATION_LENGTH'] = len(id2relation)
config['POS_LENGTH'] = len(id2pos)
config['NUM_INSTANCE'] = num_instance
print('saving...')
with open(save, "wb") as f:
    pickle.dump(config, f)
    pickle.dump(id2relation, f)
    pickle.dump(embedding_samples, f)
    pickle.dump(postag_samples, f)
    pickle.dump(position1_samples, f)
    pickle.dump(position2_samples, f)
    pickle.dump(labels, f)
