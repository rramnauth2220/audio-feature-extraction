# dependencies 
from extractors import *
from parsers import *
from classifiers import *
from listen import *
from helpers import *
from optimizing import *

# preprocessing
from sklearn.preprocessing import LabelEncoder, QuantileTransformer
from sklearn.metrics import classification_report, confusion_matrix, roc_curve, roc_auc_score, precision_recall_curve, f1_score, auc
from itertools import product
from sklearn import model_selection

# classifiers
import joblib

'''
# play and record environmental samples
fs = 44100  # sample rate
audio_samples = get_files('notebooks/youtube/clips/', ['.wav']) # samples to play and record
write_directory = 'notebooks/youtube/recordings/' # dir to write environmental recordings to

# play and record directory of samples --> TODO:( parse --> classify )
record_directory(audio_samples, write_directory, fs)
'''

# parsing from an existing feature set
df_model_set = read_features_from_file("test sets/finalmodel16bit.csv")

df_audio = read_features_from_file("test sets/all_features.csv")
df_5 = read_features_from_file("test sets/5s-200.csv")
df_10 = read_features_from_file("test sets/10s-200.csv")
df_recordings = read_features_from_file("test sets/5s-200-recordings.csv")
df_model_set = df_model_set.fillna(0)
#prefix = "5S_"

# naming classifiers
names = [
    'K Nearest Neighbors', 
    # 'Linear SVM', 
    # 'RBF SVM',
    # 'Gaussian Process', 
    # 'Decision Tree', 
    # 'Random Forest', 
    # 'Neural Net', 
    # 'AdaBoost', 
    # 'Naive Bayes', 
    # 'QDA'
]

# defining classifier and their parameters
classifiers = [
    KNeighborsClassifier(3), # number of neighbors = 3
    # SVC(kernel='linear', C=0.025, probability=True), # linear kernel with regularization/misclassification error = 0.025
    # SVC(gamma=2, C=0.025, probability=True), # looser SVM with higher regularization
    # GaussianProcessClassifier(1.0 * RBF(1.0)), # RBF kernel
    # DecisionTreeClassifier(max_depth=5),
    # RandomForestClassifier(max_depth=5, n_estimators=10, max_features=1), # estimators = # of trees in the forest, max_features = # of features to consider when looking for best split
    # MLPClassifier(alpha=0.025, max_iter=1000), # multilayer perceptron with L2 penalty/regularization = 1, max_iter = limit as solver iterates until convergence
    # AdaBoostClassifier(), 
    # GaussianNB(),
    # QuadraticDiscriminantAnalysis()
]

# referenced tests
tests = [
#    #{ "name": "Other Test", "file": "test sets/morechimeandtv.csv", "results": [] },
#    #{ "name": "Podcast Test", "file": "test sets/drama_podcast_reality.csv", "results": [] }
]

# test and train classifiers
def evaluate_classifiers(names, classifiers, dataset, tests, prefix, output):
    models = []

    # dataframe components
    scores = []
    accuracy_vals = []
    recall_vals = []
    specificity_vals = []
    precision_vals = []
    false_positive_rates = []
    false_negative_rates = []
    cv_means = []
    cv_stds = []
    no_skill_aucs = []
    logistic_aucs = []
    prc_aucs = []
    prc_f1_scores = []
    lr_precisions = []
    lr_recalls = []

    # split data into train/test
    print("splitting dataset")
    X = dataset.drop(['target'], axis = 1).values
    y = dataset['target']
    X = QuantileTransformer(output_distribution='normal').fit_transform(X)
    X_train, X_test, y_train, y_test = \
         train_test_split(X, y, test_size=.25, random_state=42)
    print("completing dataset test/train split")

    for name, clf in zip(names, classifiers):
        print("CLASSIFIER", clf)
        
        selector = SelectKBest(score_func=f_classif)
        results = grid_search(X, y, clf, selector, name, "ANOVA")

        print('Best Mean Accuracy: %.3f' % results.best_score_)
        print('Best Config: %s' % results.best_params_)
        print('Best No. of Dimensions: %d' % np.array(list(results.best_params_.values()))[0])

        print("updating k in feature selection")
        k = np.array(list(results.best_params_.values()))[0] # number of features to select

        #k = 259
        selector = SelectKBest(score_func=f_classif, k=k)

        X_train_fs, X_test_fs, fs = \
             select_features(X_train, y_train, X_test, k, selector)
        clf.fit(X_train_fs, y_train)
        print("X_TRAINING DIMENSIONS:", X_train_fs)

        print('ORIGINAL: %s, REDUCED: %s' % (X_train.shape, X_train_fs.shape))

        # record scores for the features
        print('compiling feature distribution output')
        k_df = pd.DataFrame(columns = ['Feature', 'K', 'p'])
        for i in range(len(fs.scores_)):
            k_df = k_df.append({'Feature' : dataset.columns[i], 'K' : fs.scores_[i], 'p' : fs.pvalues_[i]}, ignore_index=True)    
        k_df.to_csv('models/' + prefix + name + '_features_scores.csv')

        print('printing k important features')
        importances = k_df.nlargest(k, 'K')
        f = open('models/' + prefix + name + '_features.txt', "w")
        f.write("&&".join(importances['Feature']))
        f.close()
        print(importances)

        print('computing classifier performance metrics')
        score = clf.score(X_test_fs, y_test)
        scores.append(score)

        y_hat = clf.predict(X_test_fs)
        models.append(clf)

        # train classifier
        # clf.fit(X_train, y_train)
        
        # score = clf.score(X_test, y_test)
        # scores.append(score)
        
        # build classifier model
        # y_hat = clf.predict(X_test)
        # models.append(clf) # save model
        
        # compute basic performance metrics
        tn, fp, fn, tp = confusion_matrix(y_test, y_hat).ravel()
        accuracy_vals.append((tn + tp) / (tn + fp + fn + tp))       # accuracy
        recall_vals.append(tp / (fn + tp))                          # recall
        specificity_vals.append(tn / (tn + fp))                     # specificity
        precision_vals.append(tp / (fp + tp))                       # precision
        false_positive_rates.append(fp / (tn + fp))                 # false positive rate
        false_negative_rates.append(fn / (fn + tp))                 # false negative rate
        print(name, classification_report(y_test, y_hat))
        
        # cross validation score
        kfold = model_selection.KFold(n_splits=10)                  
        cv_score = model_selection.cross_val_score(clf, X, y, cv=kfold)
        cv_means.append(cv_score.mean() * 100.0)
        cv_stds.append(cv_score.std() * 100.0)
        
        # logistical roc auc
        # lr_probs_roc = clf.predict_proba(X_test)[:, 1]
        try:
            lr_probs_roc = clf.predict_proba(X_test_fs)[:, 1]                
            lr_auc_roc = roc_auc_score(y_test, lr_probs_roc)
            logistic_aucs.append(lr_auc_roc)

            # no skill roc auc  
            ns_probs_roc = [0 for _ in range(len(y_test))]                  
            ns_auc_roc = roc_auc_score(y_test, ns_probs_roc)
            no_skill_aucs.append(ns_auc_roc)
        except Exception as ex:
            print(str(type(clf)) + " may not support predicting probabilities:" + str(type(ex)))
            logistic_aucs.append(-1)
            no_skill_aucs.append(-1)

        # roc auc curves
        # ns_fpr, ns_tpr, _ = roc_curve(y_test, ns_probs)           
        # lr_fpr, lr_tpr, _ = roc_curve(y_test, lr_probs)
        
        # precision-recall curves
        try:
            lr_precision, lr_recall, _ = precision_recall_curve(y_test, lr_probs_roc)
            lr_precisions.append(lr_precision)
            lr_recalls.append(lr_recall)
            lr_f1_prc, lr_auc_prc = f1_score(y_test, y_hat), auc(lr_recall, lr_precision)
        except Exception as ex:
            print(str(type(clf)) + " may not support predicting probabilities:" + str(type(ex)))
            lr_precisions.append(-1)
            lr_recalls.append(-1)

        try:
            prc_aucs.append(lr_auc_prc)
            prc_f1_scores.append(lr_f1_prc)
            no_skill = len(y_test[y_test==1]) / len(y_test)
        except Exception as ex:
            print(str(type(clf)) + " may not support predicting probabilities:" + str(type(ex)))
            prc_aucs.append(-1)
            prc_f1_scores.append(-1)

        # save model
        filename = 'models/' + prefix + name +  '.sav'
        joblib.dump(clf, filename)
        print("saved model:", filename)

        # testing suite
        for test in tests:
            samples = pd.read_csv(test["file"])
            
            samples_X = samples.drop(['target'], axis = 1)
            print(importances['Feature'].to_numpy())
            samples_X.drop(samples_X.columns.difference(importances['Feature'].to_numpy()), axis = 1, inplace=True)
            samples_y = samples['target']
            samples_X = QuantileTransformer(output_distribution='normal').fit_transform(samples_X)
            predictions = clf.predict(samples_X)
            print("TEST (", test["name"], ")", classification_report(samples_y, predictions))
            # tn, fp, fn, tp = confusion_matrix(samples_y, predictions).ravel()
            # test["results"].append((tn + tp) / (tn + fp + fn + tp))
            test['results'].append(accuracy_score(samples_y, predictions))
    
    # compile performance metrics into output
    print("compiling performance dataframe")
    df_performance = pd.DataFrame({
        'classifier': names, 
        'score': scores, 
        'accuracy': accuracy_vals, 
        'recall': recall_vals,
        'specificity': specificity_vals,
        'precision': precision_vals,
        'FPR': false_positive_rates,
        'FNR': false_negative_rates, 
        'CV-10 mean': cv_means,
        'CV-10 std': cv_stds, 
        'No Skill ROC AUC': no_skill_aucs,
        'Logistic ROC AUC': logistic_aucs,
        'Precision-Recall AUC': prc_aucs,
        'F1': prc_f1_scores
    })

    # record test evaluations as separate columns
    for test in tests:
        df_performance[test["name"]] = test["results"]

    print("exporting performance dataframe")
    df_performance.to_csv(prefix + output)    

    return models

# save models and their performance evals
# models_5 = evaluate_classifiers(names, classifiers, df_5, tests, "5S_", "performance_metrics.csv")
# models_10 = evaluate_classifiers(names, classifiers, df_10, tests, "10S_", "performance_metrics.csv")
# models_r5 = evaluate_classifiers(names, classifiers, df_recordings, tests, "R-5S_", "performance_metrics.csv")

models_all = evaluate_classifiers(names, classifiers, df_model_set, tests, "ANOVA_KNN_", "ANOVA_KNN_performance.csv")

# for i in range(0, len(models)):
#    filename = 'models/' + names[i] +  '.sav'
#    joblib.dump(models[i], filename)
#    print("saved model:", filename)

'''
# play and record environmental samples
fs = 44100  # sample rate
audio_samples = get_files('live tests/', ['.wav']) # samples to play and record
write_directory = 'live tests/recordings/' # dir to write environmental recordings to

# play and record directory of samples --> TODO:( parse --> classify )
# record_directory(items, write_directory, fs)

# play --> record --> parse each sample
for audio_sample in audio_samples:

    # get environmental sample
    loc = record_file(audio_sample, write_directory, fs)

    # extract features from environmental sample
    features = extract_file_features(file=loc, target=-1) #, filter_band = True, filter_directory = 'live tests/filters/') # DEBUG: update to full parse
    features.to_csv("live tests/features/" + os.path.splitext(path_leaf(loc))[0] + ".csv")

# get true targets and samples to classify
classifications = pd.read_csv("live tests/classifications.csv")                 # true targets and file pointers to classify
features_directory = "live tests/debug/"                                        # dir of feature sets of environmental samples # DEBUG: update to 'test/features/'
new_samples = get_files(directory = features_directory, valid_exts = ['.csv'])  # collect feature sets

# set up output of results
df_results = pd.DataFrame()
df_results["file"] = new_samples    # row for each sample
for name in names:                  # column for each classifier
    df_results[name] = 0

# classify environmental samples
j = 0 # which sample are we evaluating? 
for new_sample in new_samples:

    # read sample-specific feature set
    print("reading features of", new_sample)
    features = pd.read_csv(new_sample)

    # predict class using each classifier model
    i = 0 # which model are we evaluating?
    for model in models:        
        classification = get_classification(features, model)
        print(
            "MODEL:", model,
            "SAMP:", (os.path.splitext(path_leaf(new_sample))[0] + ".wav"),
            "LOCA:", (classifications.loc[classifications['file'] == (os.path.splitext(path_leaf(new_sample))[0] + ".wav")].iloc[0]["target"]),
            "CORR:", (classification[0] == (classifications.loc[classifications['file'] == (os.path.splitext(path_leaf(new_sample))[0] + ".wav")].iloc[0]["target"]))
        )
        
        # write whether the classifier got it right (1 = True, 0 = False)
        df_results.at[j, names[i]] = int(classification[0] == classifications.loc[classifications['file'] == (os.path.splitext(path_leaf(new_sample))[0] + ".wav")].iloc[0]["target"])
        i = i + 1
    j = j + 1

# compile results output
df_results.to_csv("live tests/results.csv")
'''
print("DONE.")