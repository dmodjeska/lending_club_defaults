
# coding: utf-8

# # Data Loading

# In[25]:

import itertools as it
import numpy as np
import os.path as op
import pandas as pd
import scipy as sp
import sklearn.preprocessing as Preprocessing
import datetime

from itertools import combinations
from sklearn.decomposition import TruncatedSVD as tSVD
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.io import mmread

from IPython.display import display, HTML


# In[26]:

### specify processed data files to generate - full/partial, partial %, and train/test
### Note: this cell is the same in both notebooks

# load and clean full dataset?
#load_full = False
load_full = True  # AMG

# if not loading and cleaning full dataset, what sample percentage?
sample_percent = 10

if load_full:
    pct_str = ""
else: # not load_full
    pct_str = str(sample_percent) + "_pct"
    
# use training or testing data to generate minor files?
minor_use_train = True
if minor_use_train:
    mode_str = "train"
else: # not minor_use_train
    mode_str = "test"
    
### set intermediate file names
dir_str = "./intermediate_files/"

processed_data_train_file = dir_str + "processed_data_" + "train" + pct_str + ".json"
processed_data_test_file = dir_str + "processed_data_" + "test" + pct_str + ".json"

nlp_data_file = dir_str + "nlp_data_" + mode_str + pct_str + ".json"
nlp_data_train_file = dir_str + "nlp_data_" + mode_str + pct_str + ".json"
term_freqs_file = dir_str + "term_freqs_" + mode_str + pct_str + ".mtx"
diff_terms_file = dir_str + "diff_terms_" + mode_str + pct_str + ".json"


# In[27]:

processed_data_train_file


# In[28]:

### load processed data
data = pd.read_json(processed_data_train_file)
data_nlp = pd.read_json(nlp_data_file)
desc_matrix_coo = mmread(term_freqs_file)
desc_matrix = sp.sparse.csr_matrix(desc_matrix_coo)
count_cols_df = pd.read_json(diff_terms_file)

count_cols_bool = count_cols_df.values > 0.0


# In[29]:

print len(data)


# In[30]:

model_loan_term = 36
data_filtered = data[data.loan_term == model_loan_term]
data_filtered = data_filtered[pd.to_datetime(data_filtered.issue_date).dt.year.isin([2011,2012,2013])]
print len(data_filtered)


# In[31]:

pd.to_datetime(data_filtered.issue_date).dt.year.value_counts()


# In[32]:

# del x['verif_status']
data_filtered.describe().T


# In[33]:

# earliest_credit is not really a good indicator -- we want to know how long has elapsed since then
# See http://stackoverflow.com/questions/17414130/pandas-datetime-calculate-number-of-weeks-between-dates-in-two-columns
data_filtered['months_since_earliest_credit'] = (
    (pd.to_datetime(data_filtered.issue_date) - pd.to_datetime(data_filtered.earliest_credit))/np.timedelta64(1,'M')
).round()


# In[34]:

data_filtered.columns


# In[35]:

data_filtered_x = data_filtered.drop('loan_status', axis = 1)
data_filtered_y = data_filtered['loan_status']


# In[36]:

# copy unstandardized columns for later profit calculation
profit_data = data_filtered_x[['installment', 'loan_amount', 'recoveries']]
recoveries_avg = profit_data.recoveries.sum() / float(np.count_nonzero(profit_data.recoveries))
data_filtered_x = data_filtered_x.drop('recoveries', axis = 1)


# In[38]:

# Certain columns in the raw data should not be in our model
columns_not_to_expand = [
    'description',     # free-text, so don't one-hot encode (NLP is separate)
    'verif_status',    # not sure why this is here...
    'loan_subgrade',   # tainted predictor
    'id',              # unique to each row
    'interest_rate',   # tainted predictor
    'index',           # unique to each row
    'issue_date',      # not useful in future, using economic indicators instead
    'earliest_credit', # has been converted to months_since_earliest_credit
]

# Given an input matrix X and the equivalent matrix X from the training set,
#
# (1) impute missing values (as "MISSING" for categorical, since the fact that 
# the value is missing may itself be significant; and using the median value
# for continuous predictors)
#
# (2) expand categorical predictors into a set of one-hot-encoded columns 
# (using 0 and 1, and limiting ourselves to the 50 most common values in the
# training set)
#
# (3) standardize continuous predictors using the mean and stdev of the
# training set
def expand_x(x, x_orig):
    x_expanded = pd.DataFrame()
    for colname in x_orig.columns:
        if colname in columns_not_to_expand:
            continue
        print colname, x_orig[colname].dtype
        if x_orig[colname].dtype == 'object':
            values = x[colname].fillna('MISSING')
            value_columns = x_orig[colname].fillna('MISSING').value_counts().index
            if len(value_columns) > 50:
                value_columns = value_columns[:50]
            for val in value_columns:
                x_expanded[colname + '__' + val.replace(' ', '_')] = (values == val).astype(int)
        else:
            values = x[colname].fillna(x[colname].median())
            sd = np.nanstd(x_orig[colname])
            if sd < 1e-10:
                sd = 1
            x_expanded[colname] = (values - np.nanmean(x_orig[colname]))/sd
    return x_expanded


# In[39]:

data_filtered_expanded_x = expand_x(data_filtered_x, data_filtered_x)


# In[40]:

data_filtered_expanded_x.describe().T


# In[41]:

data_filtered_expanded_x.columns


# ### Split Data

# In[42]:

# Get a more manageable sample
np.random.seed(1729)
sample_flags = np.random.random(len(data_filtered_expanded_x)) <= 0.25
print "Indexes computed" 

# train set
x_expanded = data_filtered_expanded_x.iloc[sample_flags, :]
print len(x_expanded)

# test set
x_test_expanded = data_filtered_expanded_x.iloc[~sample_flags, :]
print len(x_test_expanded)


# In[43]:

# split response column
y = data_filtered_y.iloc[sample_flags]
y_test = data_filtered_y.iloc[~sample_flags]


# In[44]:

# split profit data
profit_data_train = profit_data.iloc[sample_flags, :]
profit_data_test = profit_data.iloc[~sample_flags, :]


# In[45]:

### filter NLP data
filter_flags = data_nlp.loan_term.values == model_loan_term
data_nlp_filtered = data_nlp.iloc[filter_flags]

x_nlp_filtered = data_nlp_filtered.drop('loan_status', 1)
y_nlp_filtered = data_nlp_filtered.loan_status

desc_matrix_filtered = desc_matrix[filter_flags]
count_cols_bool_filtered = count_cols_bool[filter_flags]


# In[46]:

### split NLP data into training and testing sets
np.random.seed(1729)
train_flags = np.random.random(data_nlp_filtered.shape[0]) < 0.7

x_nlp_train = x_nlp_filtered.iloc[train_flags, :]
y_nlp_train = y_nlp_filtered.iloc[train_flags]

x_nlp_test = x_nlp_filtered.iloc[~train_flags, :]
y_nlp_test = y_nlp_filtered.iloc[~train_flags]

desc_matrix_train = pd.DataFrame(desc_matrix_filtered[train_flags, :].toarray())
desc_matrix_test = pd.DataFrame(desc_matrix_filtered[~train_flags, :].toarray())

count_cols_bool_train = pd.DataFrame(count_cols_bool_filtered[train_flags, :])
count_cols_bool_test = pd.DataFrame(count_cols_bool_filtered[~train_flags, :])

years_nlp = pd.to_datetime(x_nlp_train.issue_date).dt.year
years_nlp_test = pd.to_datetime(x_nlp_test.issue_date).dt.year


# In[47]:

### match indexes

desc_matrix_train.index = x_nlp_train.index
desc_matrix_test.index = x_nlp_test.index

count_cols_bool_train.index = x_nlp_train.index
count_cols_bool_test.index = x_nlp_test.index


# In[48]:

# inspect test proportion of good/bad loans
y_test.value_counts()


# In[49]:

# verify size of train set
np.count_nonzero(x_expanded.loan_amount)


# In[50]:

# be prepared to split stuff up by year of issue
years = pd.to_datetime(data_filtered_x.issue_date.iloc[sample_flags]).dt.year
years_test = pd.to_datetime(data_filtered_x.issue_date.iloc[~sample_flags]).dt.year


# ### Apply PCA to predictors

# In[51]:

tsvd = tSVD(n_components = 100)
data_filtered_expanded_x_pca = pd.DataFrame(tsvd.fit_transform(data_filtered_expanded_x))
data_filtered_expanded_x_pca.index = data_filtered_expanded_x.index
pca_cum_var_expl = np.cumsum(np.round(tsvd.explained_variance_ratio_, 4) * 100)


# In[52]:

print "PCA: first and last columns where % variance explained >= 99:",             np.where(pca_cum_var_expl >= 99)[0][[0, -1]]

x_expanded_pca = data_filtered_expanded_x_pca.iloc[sample_flags, :73]
x_test_expanded_pca = data_filtered_expanded_x_pca.iloc[~sample_flags, :73]


# In[53]:

tsvd = tSVD(n_components = 500)
desc_matrix_filtered_pca = pd.DataFrame(tsvd.fit_transform(desc_matrix_filtered))
desc_matrix_filtered_pca.index = x_nlp_filtered.index
pca_cum_var_expl = np.cumsum(np.round(tsvd.explained_variance_ratio_, 4) * 100)


# In[54]:
try:
    print "PCA: first and last columns where % variance explained >= 85:",             np.where(pca_cum_var_expl >= 85)[0][[0, -1]]
except:
    print "Exception!"

# In[55]:

desc_matrix_pca = desc_matrix_filtered_pca.iloc[train_flags, :]
desc_matrix_test_pca = desc_matrix_filtered_pca.iloc[~train_flags, :]

