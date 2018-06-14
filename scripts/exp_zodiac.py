import sys, os
import pdb
import json
dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, dir_path + '/..')
#sys.path.append(os.path.abspath(os.path.join(dir_path + '/..', 'config')))
#sys.path.append(os.path.abspath(os.path.join('..', 'config')))

from plastering.inferencers.zodiac_new import ZodiacInterface
from plastering.metadata_interface import *
import pdb

EXP_NUM = 4

#target_buildings = ['ebu3b', 'uva_cse', 'sdh']
#target_buildings = ['sdh']
target_buildings = ['ghc']

inferencers = {
    'zodiac': ZodiacInterface,
}


for inferencer_name, Inferencer in inferencers.items():
    for exp_id in range(0, EXP_NUM):
        for target_building in target_buildings:
            # Select labeled srcids (Not all the data are labeled yet.)
            labeled_list = LabeledMetadata.objects(building=target_building)
            target_srcids = [labeled['srcid'] for labeled in labeled_list]

            #zodiac = ZodiacInterface(target_building=target_building,
            #                         target_srcids=target_srcids)
            #zodiac.learn_auto() # This should include evaluate function for each step
            inferencer = Inferencer(target_building =target_building,
                                    target_srcids=target_srcids)
            inferencer.learn_auto()
            history = [{
                'metrics': hist['metrics'],
                'learning_srcids': len(hist['total_training_srcids'])
            } for hist in inferencer.history]
            with open('result/pointonly_notransfer_{0}_{1}_{2}.json'
                      .format(inferencer_name, target_building, exp_id), 'w') \
                    as fp:
                json.dump(history, fp)
