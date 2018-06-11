import numpy as np
import re
import time
import pdb

from sklearn.feature_extraction.text import CountVectorizer as CV
from sklearn.preprocessing import LabelEncoder as LE

from .algorithm.transfer_learning import transfer_learning
from . import Inferencer
from ..timeseries_interface import *
from ..metadata_interface import *
from ..data_feature_extractor import *


def get_name_features(names):

    name = []
    for i in names:

        s = re.findall('(?i)[a-z]{2,}',i)
        name.append(' '.join(s).lower())

    cv = CV(analyzer='char_wb', ngram_range=(3,4))
    fn = cv.fit_transform(name).toarray()

    return fn


def get_data_features(building, start_time, end_time):

    res = read_from_db(building, start_time, end_time)

    X = []
    srcids = []
    #for point, data in res.items():
    for labeled in LabeledMetadata.objects(building=building):
        srcid = labeled.srcid
        data = res[srcid]
        #t0 = time.clock()
        #TODO: better handle the dimension, it's really ugly now

        #computing features on long sequence is really slow now, so only loading a small port of the readings now
        X.append( data['data'][:3000] )
        srcids.append(srcid)
        #print (time.clock() - t0)

    dfe = data_feature_extractor( np.asarray(X) )
    fd = dfe.getF_2015_Hong()

    print ( 'data features for %s with dim:'%building, fd.shape)
    return srcids, fd


def get_namefeatures_labels(building):

    srcids = [point['srcid'] for point in LabeledMetadata.objects(building=building)]

    pt_type = [LabeledMetadata.objects(srcid=srcid).first().point_tagset.lower() for srcid in srcids]
    pt_name = [RawMetadata.objects(srcid=srcid).first().metadata['VendorGivenName'] for srcid in srcids]

    fn = get_name_features(pt_name)
    print ('%d point names loaded for %s'%(len(pt_name), building))

    return { srcid:[name_feature, label] for srcid,name_feature,label in zip(srcids,fn, pt_type) }


class BuildingAdapterInterface(Inferencer):

    def __init__(self,
                 target_building,
                 target_srcids,
                 source_buildings,
                 config={},
                 ):
        super(BuildingAdapterInterface, self).__init__(
            target_building=target_building,
            source_buildings=[src for src in source_buildings], #TODO: Jason: What is this?
            target_srcids=target_srcids
        )

        #gather the source/target data and name features, labels
        '''
        #old block loading from pre-computed files
        input1 = np.genfromtxt('../data/rice_hour_sdh', delimiter=',')
        input2 = np.genfromtxt('../data/keti_hour_sum', delimiter=',')
        input3 = np.genfromtxt('../data/sdh_hour_rice', delimiter=',')
        input2 = np.vstack((input2, input3))
        fd1 = input1[:, 0:-1]
        fd2 = input2[:, 0:-1]

        train_fd = fd1
        test_fd = fd2
        train_label = input1[:, -1]
        test_label = input2[:, -1]

        pt_name = [i.strip().split('\\')[-1][:-5] for i in open('../data/rice_pt_sdh').readlines()]
        test_fn = get_name_features(pt_name)
        '''
        #TODO: handle multiple source buildings

        if 'source_time_ranges' in config:
            self.source_time_ranges = config['source_time_ranges']
        else:
            self.source_time_ranges = [(DEFAULT_START_TIME, DEFAULT_END_TIME)]\
                * len(source_buildings)
        if 'target_time_range' in config:
            self.target_time_range = config['target_time_range']
        else:
            self.target_time_range = (DEFAULT_START_TIME, DEFAULT_END_TIME)

        source_building = source_buildings[0]

        #data features
        source_ids, train_fd = get_data_features(source_building,
                                                 self.source_time_ranges[0][0],
                                                 self.source_time_ranges[0][1])
        target_ids, test_fd = get_data_features(target_building)

        #name features, labels
        source_res = get_namefeatures_labels(source_building)
        train_label = [source_res[srcid][1] for srcid in source_ids]

        target_res = get_namefeatures_labels(target_building)
        test_fn = [target_res[tgtid][0] for tgtid in target_ids]
        test_label = [target_res[tgtid][1] for tgtid in target_ids]

        #find the label intersection
        intersect = set(test_label) & set(train_label)
        print ('intersected tagsets:', intersect)

        #preserve the intersection, get ids for indexing data feature matrices
        if intersect:
            train_filtered = [[i,j] for i,j in enumerate(train_label) if j in intersect]
            train_id, train_label = [list(x) for x in zip(*train_filtered)]
            test_filtered = [[i,j] for i,j in enumerate(test_label) if j in intersect]
            test_id, test_label = [list(x) for x in zip(*test_filtered)]
        else:
            raise ValueError('no common labels!')

        train_fd = train_fd[train_id, :]
        test_fd = test_fd[test_id, :]
        test_fn = test_fn[test_id, :]

        le = LE()
        le.fit(intersect)
        train_label = le.transform(train_label)
        test_label = le.transform(test_label)


        self.learner = transfer_learning(
            train_fd,
            test_fd,
            train_label,
            test_label,
            test_fn,
        )


    def predict(self):

        preds, labeled_set = self.learner.predict()

        return preds, labeled_set


    def run_auto(self):

        self.learner.run_auto()

