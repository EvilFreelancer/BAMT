import numpy as np

import pickle
import joblib
import random
import itertools

from .base import BaseNode
from .schema import LogitParams
from bamt.log import logger_nodes

from sklearn import linear_model
from pandas import DataFrame
from typing import Optional, List, Union, Dict


class ConditionalLogitNode(BaseNode):
    """
    Main class for Conditional Logit Node
    """

    def __init__(self, name: str, classifier: Optional[object] = None):
        super(ConditionalLogitNode, self).__init__(name)
        if classifier is None:
            classifier = linear_model.LogisticRegression(
                multi_class='multinomial', solver='newton-cg', max_iter=100)
        self.classifier = classifier
        self.type = 'ConditionalLogit' + f" ({type(self.classifier).__name__})"

    def fit_parameters(self, data: DataFrame) -> Dict[str, Dict[str, LogitParams]]:
        """
        Train params on data
        Return:
        {"hybcprob": {<combination of outputs from discrete parents> : LogitParams}}
        """
        hycprob = dict()
        values = []
        combinations = []
        for d_p in self.disc_parents:
            values.append(np.unique(data[d_p].values))
        for xs in itertools.product(*values):
            combinations.append(list(xs))
        for comb in combinations:
            mask = np.full(len(data), True)
            for col, val in zip(self.disc_parents, comb):
                mask = (mask) & (data[col] == val)
            new_data = data[mask]
            # mean_base = [np.nan]
            classes = [np.nan]
            key_comb = [str(x) for x in comb]
            if new_data.shape[0] != 0:
                model = self.classifier
                values = set(new_data[self.name])
                if len(values) > 1:
                    model.fit(new_data[self.cont_parents].values,
                              new_data[self.name].values)
                    classes = list(model.classes_)
                    serialization = self.choose_serialization(model)

                    if serialization == 'pickle':
                        ex_b = pickle.dumps(self.classifier, protocol=4)
                        model_ser = ex_b.decode('latin1')

                        # model_ser = pickle.dumps(self.classifier, protocol=4)
                        hycprob[str(key_comb)] = {'classes': classes,
                                                  'classifier_obj': model_ser,
                                                  'classifier': type(self.classifier).__name__,
                                                  'serialization': 'pickle'}
                    else:
                        logger_nodes.warning(
                            f"{self.name} {comb}::Pickle failed. BAMT will use Joblib. | " + str(serialization.args[0]))

                        path = self.get_path_joblib(node_name=self.name.replace(' ', '_'),
                                                    specific=comb)
                        joblib.dump(model, path, compress=True, protocol=4)

                        hycprob[str(key_comb)] = {'classes': classes,
                                                  'classifier_obj': path,
                                                  'classifier': type(self.classifier).__name__,
                                                  'serialization': 'joblib'}
                else:
                    classes = list(values)
                    hycprob[str(key_comb)] = {'classes': classes, 'classifier': type(
                        self.classifier).__name__, 'classifier_obj': None, 'serialization': None}

            else:
                hycprob[str(key_comb)] = {'classes': list(classes), 'classifier': type(
                    self.classifier).__name__, 'classifier_obj': None, 'serialization': None}
        return {"hybcprob": hycprob}

    @staticmethod
    def choose(node_info: Dict[str, Dict[str, LogitParams]],
               pvals: List[Union[str, float]]) -> str:
        """
        Return value from ConditionalLogit node
        params:
        node_info: nodes info from distributions
        pvals: parent values
        """

        dispvals = []
        lgpvals = []
        for pval in pvals:
            if isinstance(pval, str):
                dispvals.append(pval)
            else:
                lgpvals.append(pval)

        if any(parent_value == 'nan' for parent_value in dispvals):
            return np.nan

        lgdistribution = node_info["hybcprob"][str(dispvals)]

        # JOBLIB
        if len(lgdistribution["classes"]) > 1:
            if lgdistribution["serialization"] == 'joblib':
                model = joblib.load(lgdistribution["classifier_obj"])
            else:
                # str_model = lgdistribution["classifier_obj"].decode('latin1').replace('\'', '\"')
                bytes_model = lgdistribution["classifier_obj"].encode('latin1')
                model = pickle.loads(bytes_model)

            distribution = model.predict_proba(
                np.array(lgpvals).reshape(1, -1))[0]

            rand = random.random()
            rindex = 0
            lbound = 0
            ubound = 0
            for interval in range(len(lgdistribution["classes"])):
                ubound += distribution[interval]
                if lbound <= rand < ubound:
                    rindex = interval
                    break
                else:
                    lbound = ubound
            return str(lgdistribution["classes"][rindex])

        else:
            return str(lgdistribution["classes"][0])

    @staticmethod
    def predict(node_info: Dict[str, Dict[str, LogitParams]],
                pvals: List[Union[str, float]]) -> str:
        """
        Return value from ConditionalLogit node
        params:
        node_info: nodes info from distributions
        pvals: parent values
        """

        dispvals = []
        lgpvals = []
        for pval in pvals:
            if isinstance(pval, str):
                dispvals.append(pval)
            else:
                lgpvals.append(pval)

        lgdistribution = node_info["hybcprob"][str(dispvals)]

        # JOBLIB
        if len(lgdistribution["classes"]) > 1:
            if lgdistribution["serialization"] == 'joblib':
                model = joblib.load(lgdistribution["classifier_obj"])
            else:
                # str_model = lgdistribution["classifier_obj"].decode('latin1').replace('\'', '\"')
                bytes_model = lgdistribution["classifier_obj"].encode('latin1')
                model = pickle.loads(bytes_model)

            pred = model.predict(np.array(lgpvals).reshape(1, -1))[0]

            return str(pred)

        else:
            return str(lgdistribution["classes"][0])
