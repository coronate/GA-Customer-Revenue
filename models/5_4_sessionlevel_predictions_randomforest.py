import pandas as pd
import numpy as np
from sklearn.metrics import mean_squared_error
import time
from pandas.core.common import SettingWithCopyWarning
import warnings
import lightgbm as lgb
from sklearn.model_selection import GroupKFold
from sklearn.ensemble import RandomForestRegressor, AdaBoostRegressor, \
                             BaggingRegressor, ExtraTreesRegressor, \
                             GradientBoostingRegressor


#df_train = pd.read_csv("../input/df_train-flattened.csv", index=False)
selected_features = pd.read_csv("../input/selected_features_persession.csv")
selected_features = selected_features["selected_features"]
df_train = pd.read_csv("../input/df_train_prepared.csv")
df_train = df_train.sample(10000, random_state = 100)
df_test =  pd.read_csv("../input/df_test_prepared.csv")   #<-EXECUTE FEATURE SELECTION


y_reg = df_train['totals.transactionRevenue'].fillna(0)

df_train = df_train[selected_features]
df_test  = df_test[selected_features]
df_test["fullVisitorId"] = df_test["fullVisitorId"].astype(str)
df_train["fullVisitorId"] = df_train["fullVisitorId"].astype(str)
#Get session target

#Define folding strategy
def get_folds(df=None, n_splits=5):
    """Returns dataframe indices corresponding to Visitors Group KFold"""
    # Get sorted unique visitors
    unique_vis = df['fullVisitorId'].unique()

    # Get folds
    folds = GroupKFold(n_splits=n_splits)
    fold_ids = []
    ids = np.arange(df.shape[0])
    for trn_vis, val_vis in folds.split(X=unique_vis, y=unique_vis, groups=unique_vis):
        fold_ids.append(
            [
                ids[df['fullVisitorId'].isin(unique_vis[trn_vis])],
                ids[df['fullVisitorId'].isin(unique_vis[val_vis])]
            ]
        )

    return fold_ids


folds = get_folds(df=df_train, n_splits=5)

#-------------------- Predict revenues at session level-----------------


importances = pd.DataFrame()
oof_reg_preds = np.zeros(df_train.shape[0])
sub_reg_preds = np.zeros(df_test.shape[0])

df_test_fullvisitorid_str = df_test["fullVisitorId"].copy()
df_test["fullVisitorId"] = df_test["fullVisitorId"].astype(float)

for fold_, (trn_, val_) in enumerate(folds):
    trn_x, trn_y = df_train.iloc[trn_], y_reg.iloc[trn_]
    val_x, val_y = df_train.iloc[val_], y_reg.iloc[val_]

    trn_x["fullVisitorId"] = trn_x["fullVisitorId"].astype(float)
    val_x["fullVisitorId"] = val_x["fullVisitorId"].astype(float)


    reg = RandomForestRegressor(
           bootstrap=True, criterion='mse',
           max_depth=None,
           max_features='auto',
           max_leaf_nodes=None,
           min_impurity_decrease=0.0,
           min_impurity_split=None,
           min_samples_leaf=1,
           min_samples_split=2,
           min_weight_fraction_leaf=0.0,
           n_estimators=200, 
           n_jobs=8,
           oob_score=False, 
           random_state=None,
           verbose= True,
           warm_start=False)


    reg.fit(trn_x, np.log1p(trn_y)  )

    oof_reg_preds[val_] = reg.predict(val_x)
    oof_reg_preds[oof_reg_preds < 0] = 0

    _preds = reg.predict(df_test)
    _preds[_preds < 0] = 0
    sub_reg_preds += np.expm1(_preds) / len(folds)
    
mean_squared_error(np.log1p(y_reg), oof_reg_preds) ** .5

pass_columns = ["fullVisitorId", "predictions_xgboost"]
df_train['predictions_randomforest'] = np.expm1(oof_reg_preds)
df_train['totals.transactionRevenue'] = y_reg 
df_test['predictions_randomforest'] = sub_reg_preds
df_test["fullVisitorId"] = df_test_fullvisitorid_str

df_train.to_csv("../input/df_train_session_randomforest.csv", index = False)
df_test.to_csv("../input/df_test_session_randomforest.csv", index = False)


