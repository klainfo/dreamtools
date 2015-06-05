import numpy as np
import glob
import pandas as pd
import os
from cno.misc.profiler import do_profile


class D7C1(object):
    """
        Official, we provide only the scoring functions but additional tools
        such as draft version of the NULL distribution + pvalues are provided.


        s = D7C1()
        s.score_model1_prediction(filename)
        s.score_model1_parameters(filename)

        s.summary() returns scores of the participants (if you have the files)

    """

    def __init__(self, path='submissions'):

        self.path = path

        teams = glob.glob(path + os.sep +'*')
        self.teams = [this for this in teams if os.path.isdir(this) is True]


        self.N = len(self.teams)
        self.distances = np.zeros((self.N, 4))
        self.pvalues = np.zeros((self.N, 4))

        self.scores = {}
        self._load_gold_standard()
        self._load_submissions()
        self.compute_score_distance_model1()
        self.compute_score_parameter_prediction_model1()
        
        # data structure to store null distances
        self.rdistance_pred1 = [] 
        self.rdistance_param1 = []

    def _load_submissions(self):

        tag_param1 = 'dream7_netparinf_parameters_model_1'
        tag_param2 = 'dream7_netparinf_parameters_model_2'
        tag_pred1 = 'dream7_netparinf_timecourse_model_1'
        tag_topo2 = 'dream7_netparinf_networktopo_model_2'

        self.data = {}
        self.data['param1'] = {}
        self.data['param2'] = {}
        self.data['pred1'] = {}
        self.data['topo2'] = {}
        self.team_names = []
        for team in self.teams:
            team_name = team.split(os.sep)[1]
            self.team_names.append(team_name)
            
            filename = team + os.sep + tag_param1 + '_' + team_name + '.txt'
            self.data['param1'][team_name] = self._read_df(filename, 'param')
        
            filename = team + os.sep + tag_param2 + '_' + team_name + '.txt'
            self.data['param2'][team_name] = self._read_df(filename, 'param')

            filename = team + os.sep + tag_pred1 + '_' + team_name + '.txt'
            self.data['pred1'][team_name] = self._read_df(filename, 'pred')

            filename = team + os.sep + tag_topo2 + '_' + team_name + '.txt'
            self.data['topo2'][team_name] = self._read_df(filename, 'topo')

    def _read_df(self, filename, mode, sep='\s+'):
        try:
            if mode == 'param':
                df = pd.read_csv(filename, sep=sep, index_col=0, 
                    header=None, names=['values'])
            elif mode == 'pred':
                df = pd.read_csv(filename, sep=sep, index_col=0)
            elif mode == 'topo':
                df = pd.read_csv(filename, sep=sep, index_col=None, header=None,
                        names=['g1','sign1','g2','sign2','g3'])
        except Exception as err:
            print filename
            print(err)
            df = None
        return df

    def score_model1_parameters(self, filename):
        data = self._read_df(filename, mode='param')
        distance = self._compute_score_parameter_prediction_model(data)
        return distance

    def score_model1_prediction(self, filename):
        data = self._read_df(filename, mode='pred')
        distance = self._compute_score_distance_model1(data, 10,39)
        return distance

    def _get_gs(self, filename):
        self._path2data = os.path.split(os.path.abspath(__file__))[0]
        filename = os.sep.join([self._path2data, "goldstandard", filename])
        return filename

    def _load_gold_standard(self):
        self.gs = {}
        self.gs['param1'] = self._read_df(self._get_gs("model1_parameters_answer.txt"), mode='param')
        self.gs['param2'] = self._read_df(self._get_gs("model2_parameters_answer.txt"), mode='param')
        self.gs['pred1'] = self._read_df(self._get_gs("model1_prediction_answer.txt"), mode='pred')
        self.gs['topo2'] = self._read_df(self._get_gs("model2_topology_answer.txt"), mode='topo')

    def compute_score_parameter_prediction_model1(self):
        """
        

        equation http://www.the-dream-project.org/result/network-topology-and-parameter-inference-challenge

        """
        # parameter model1
        scores = {}
        for team in self.team_names:
            data = self.data['param1'][team]
            score = self._compute_score_parameter_prediction_model(data)
            scores[team] = score
        df = pd.TimeSeries(scores)
        df = pd.DataFrame({'scores':df, 'rank':df.rank()})
        self.scores['param1'] = df.sort(columns='rank')

    def _compute_score_parameter_prediction_model(self, data):
        diff = data / self.gs['param1']
        diff = (np.log10(diff)**2).mean()
        score = diff.values[0] # should be a single float
        return score

    def compute_score_distance_model1(self, startindex=10, endindex=39):
        """

        endindex is set to 39 so it does not take into account last value at time=20
        This is to be in agreement with the implemenation used in the final leaderboard

        https://www.synapse.org/#!Synapse:syn2821735/wiki/71062

        If you want to take into account final point, set endindex to 40

        """
        scores = {}
        for team in self.team_names:
            data = self.data['pred1'][team]
            scores[team] = self._compute_score_distance_model1(data, startindex, endindex)
        self.scores['pred1'] = pd.TimeSeries(scores)
        self.scores['pred1'].sort()
        self.scores['pred1'] = self.scores['pred1'].to_frame()
        self.scores['pred1'].columns = ['scores']
       
    #@do_profile()
    def _compute_score_distance_model1(self, data, startindex, endindex):
        d1 = (self.gs['pred1'] - data) ** 2  
        d1 /= (0.01 + 0.04 * self.gs['pred1'].values**2)
        # let us ignore the first 10 points

        # faster to use numpy array and indices
        data = d1.values[startindex:endindex+1,:]
        N = endindex - startindex + 1.
        distance = np.sum(data) / (3*N)  # normalisation
        return distance

    def get_null_param1(self, N=10000):
        # select only best 9 as in the paper
        Nbest = 9
        best_teams = list(self.scores['param1'].ix[0:Nbest].index)
        
        # create a dataframe to hold all teams and 
        p = pd.DataFrame(dict([(key, self.data['param1'][key].T.values[0]) 
            for key in best_teams]))

        nulls = []
        for k in xrange(0,45):
            null = p.ix[k][np.random.randint(0, Nbest, N)]
            nulls.append(null)

        indexnames = list(self.gs['param1'].index)
        df = pd.DataFrame(dict([(name, nulls[i].values) 
            for i, name in enumerate(indexnames)]))
        df = df[self.gs['param1'].index]
        return df

    def _compute_rdist_param1(self, N=10000):
        df = self.get_null_param1(N=N)

        distances =[]
        from easydev import progress_bar
        pb = progress_bar(N)
        for i in xrange(0, N):
            df1 = df.ix[i].to_frame(name='values')
            distance = self._compute_score_parameter_prediction_model(df1)
            distances.append(distance)
            pb.animate(i, 0)
        return distances

    def _compute_pvalues_param1(self, N=10000):
        rdist = self._compute_rdist_param1(N=N)
        self.rdistance_param1.extend(rdist)
        #pvalues = [len([x for x in self.rdistance_param1 if x <=score] )/float(N) 
        #        for score in self.scores['param1'].scores]
        #self.scores['param1']['pvalues'] = pvalues

    def get_random_pred1(self, N=10000):
        Nbest = 9
        best_teams = list(self.scores['pred1'].ix[0:Nbest].index)
        print(best_teams)

        # data mangling to extract random values easily 
        p3 = pd.DataFrame(dict([(key, self.data['pred1'][key]['p3']) for key in best_teams]))
        p5 = pd.DataFrame(dict([(key, self.data['pred1'][key]['p5']) for key in best_teams]))
        p8 = pd.DataFrame(dict([(key, self.data['pred1'][key]['p8']) for key in best_teams]))

        df = self.gs['pred1'].copy()

        data = np.zeros((41,3, N))
        for ik,k in enumerate(list(self.gs['pred1'].index)):
            data[ik,0] = p3.ix[k][np.random.randint(0,Nbest,N)]
            data[ik,1] = p5.ix[k][np.random.randint(0,Nbest,N)]
            data[ik,2] = p8.ix[k][np.random.randint(0,Nbest,N)]
        return data
           
    #@do_profile()
    def _compute_rdist_pred1(self, N=10000):
        data = self.get_random_pred1() # numpy matrices

        distances = []
        from easydev import progress_bar
        pb = progress_bar(N)
        for i in xrange(0,N):
            df = data[:,:,i]
            # FIXME those values 10,39 should not be hardcoded
            distance = self._compute_score_distance_model1(df, 10,39)
            distances.append(distance)
            pb.animate(i, 0)
        return distances

    def _compute_pvalues_pred1(self ,N=10000):
        rdist = self._compute_rdist_pred1(N=N)
        self.rdistance_pred1.extend(rdist[:])
        #pvalues = [len([x for x in self.rdistance_pred1 if x <=score] )/float(N) 
        #        for score in self.scores['pred1'].scores]
        #self.scores['pred1']['pvalues'] = pvalues

    def compute_overall_score(self, N=100):
        """
        For model 1, each team obtained a p-value for the time-course 
        predictions and a p-value for the parameter predictions. The overall 
        score is -log10 of the product of these two p-values.

        """
        self._compute_pvalues_pred1(N=N)
        self._compute_pvalues_param1(N=N)
        import fitter
        fit_param1 = fitter.Fitter(self.rdistance_param1)
        fit_param1.distributions = ['beta']
        fit_param1.fit()
        fit_pred1 = fitter.Fitter(self.rdistance_pred1)
        fit_pred1.distributions = ['beta']
        fit_pred1.fit()

        import scipy.stats
        self.pvalues_param1 = scipy.stats.beta.cdf(self.scores['param1'].scores, 
                *fit_param1.fitted_param['beta'])
        self.pvalues_pred1 = scipy.stats.beta.cdf(self.scores['pred1'].scores, 
                *fit_pred1.fitted_param['beta'])

        self.scores['pred1']['pvalues'] = self.pvalues_pred1
        self.scores['param1']['pvalues'] = self.pvalues_param1


    def summary(self):

        df = pd.merge(self.scores['param1'], self.scores['pred1'], 
                left_index=True, right_index=True, 
                suffixes=['_param', '_pred'])
        return df


"""
Model 2. Relative p-value and scores
Teams   Topology prediction score   p-value for topology    OverallScore
crux    12  1.49E-02    1.83
ForeCinHD   9   5.60E-02    1.25
Synmikro    8   1.07E-01    0.97
Dreamcatcher    8   1.07E-01    0.97
Biometris   8   1.07E-01    0.97
TBP 7   2.10E-01    0.68
thetasigmabeta  6   3.83E-01    0.42
BCB 5   6.01E-01    0.22
orangeballs 4   8.01E-01    0.10
reinhardt   4   8.01E-01    0.10
2pac    3   9.86E-01    0.01
ntu 2   1.00E+00    0


"""