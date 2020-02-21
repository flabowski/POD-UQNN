"""Module for plotting results of 1D Shekel Equation."""

import os
import sys
import yaml
import matplotlib.pyplot as plt
import numpy as np


sys.path.append(os.path.join("..", ".."))
from podnn.podnnmodel import PodnnModel
from podnn.plotting import figsize, saveresultdir
from podnn.metrics import re, re_mean_std
from podnn.testgenerator import X_FILE, U_MEAN_FILE, U_STD_FILE


def get_test_data():
    dirname = "data"
    X = np.load(os.path.join(dirname, X_FILE))
    U_test_mean = np.load(os.path.join(dirname, U_MEAN_FILE))
    U_test_std = np.load(os.path.join(dirname, U_STD_FILE))
    return X, U_test_mean, U_test_std


def plot_results(U_test, U_pred, U_pred_hifi_mean, U_pred_hifi_std, sigma_pod,
                 resdir=None, train_res=None, HP=None, no_plot=False):

    X, U_test_hifi_mean, U_test_hifi_std = get_test_data()
    x = X[0]

    U_pred_mean = np.mean(U_pred, axis=-1)
    # Using nanstd() to prevent NotANumbers from appearing
    U_pred_std = np.nanstd(U_pred, axis=-1)

    U_pred_hifi_mean_sig = U_pred_hifi_mean[1]
    U_pred_hifi_std_sig = U_pred_hifi_std[1]

    U_pred_hifi_mean = U_pred_hifi_mean[0]
    U_pred_hifi_std = U_pred_hifi_std[0]

    # Compute relative error
    error_test_mean, error_test_std = re_mean_std(U_test, U_pred)
    hifi_error_test_mean = re(U_test_hifi_mean, U_pred_hifi_mean)
    hifi_error_test_std = re(U_test_hifi_std, U_pred_hifi_std)
    sigma_Thf = U_pred_hifi_mean_sig.mean(0).mean(0)
    print(f"Test relative error: mean {error_test_mean:4f}, std {error_test_std:4f}")
    print(f"HiFi test relative error: mean {hifi_error_test_mean:4f}, std {hifi_error_test_std:4f}")
    print(f"Mean Sigma on hifi predictions: {sigma_Thf:4f}")
    print(f"Mean Sigma contrib from POD: {sigma_pod:4f}")
    errors = {
        "REM_T": error_test_mean.item(),
        "RES_T": error_test_std.item(),
        "REM_Thf": hifi_error_test_mean.item(),
        "RES_Thf": hifi_error_test_std.item(),
        "sigma": sigma_Thf.item(),
        "sigma_pod": sigma_pod.item(),
    }

    if no_plot:
        return hifi_error_test_mean, hifi_error_test_std

    fig = plt.figure(figsize=figsize(1, 2, scale=2.))

    # Plotting the means
    ax1 = fig.add_subplot(1, 2, 1)
    ax1.plot(x, U_pred_mean[0], "k,", label=r"$\hat{u}_T(x)$")
    ax1.plot(x, U_pred_hifi_mean[0], "b-", label=r"$\hat{u}_{T,hf}(x)$")
    ax1.plot(x, U_test_hifi_mean[0], "r--", label=r"$u_{T,hf}(x)$")
    lower = U_pred_hifi_mean[0] - 2 * U_pred_hifi_mean_sig[0]
    upper = U_pred_hifi_mean[0] + 2 * U_pred_hifi_mean_sig[0]
    plt.fill_between(x, lower, upper, 
                     facecolor='orange', alpha=0.5, label=r"$2\sigma_{T,hf}(x)$")
    ax1.legend()
    ax1.set_title("Means")
    ax1.set_xlabel("$x$")

    # Plotting the std
    ax2 = fig.add_subplot(1, 2, 2)
    ax2.plot(x, U_pred_std[0], "k,", label=r"$\hat{u}_T(x)$")
    ax2.plot(x, U_pred_hifi_std[0], "b-", label=r"$\hat{u}_{T,hf}(x)$")
    ax2.plot(x, U_test_hifi_std[0], "r--", label=r"$u_{T,hf}(x)$")
    lower = U_pred_hifi_std[0] - 2 * U_pred_hifi_std_sig[0]
    upper = U_pred_hifi_std[0] + 2 * U_pred_hifi_std_sig[0]
    plt.fill_between(x, lower, upper, 
                     facecolor='orange', alpha=0.5, label=r"2\text{std}(\hat{u}_T(x))")
    ax2.set_title("Standard deviations")
    ax2.set_xlabel("$x$")

    saveresultdir(resdir, HP, errors, train_res)

    return hifi_error_test_mean, hifi_error_test_std


if __name__ == "__main__":
    if len(sys.argv) <= 1:
        raise FileNotFoundError("Provide a resdir")

    resdir = sys.argv[1]
    with open(os.path.join(resdir, "HP.txt")) as HPFile:
        hp = yaml.load(HPFile)

    model = PodnnModel.load(resdir)

    x_mesh = np.load(os.path.join(resdir, "x_mesh.npy"))
    _, _, _, X_v_test, U_test = model.load_train_data()

    v_pred, v_pred_sig = model.predict_v(X_v_test)
    U_pred = model.V.dot(v_pred.T)
    U_pred = model.restruct(U_pred)
    U_test = model.restruct(U_test)

    # Sample the new model to generate a HiFi prediction
    print("Sampling {n_s_tst} parameters")
    X_v_test_hifi = model.generate_hifi_inputs(hp["n_s_tst"],
                                               hp["mu_min"], hp["mu_max"])
    print("Predicting the {n_s_tst} corresponding solutions")
    U_pred_hifi, U_pred_hifi_sig = model.predict_var(X_v_test_hifi)
    U_pred_hifi_mean = (model.restruct(U_pred_hifi.mean(-1), no_s=True),
                        model.restruct(U_pred_hifi_sig.mean(-1), no_s=True))
    U_pred_hifi_std = (model.restruct(U_pred_hifi.std(-1), no_s=True),
                       model.restruct(U_pred_hifi_sig.mean(-1), no_s=True))

    # Plot against test and save
    plot_results(U_test, U_pred, U_pred_hifi_mean, U_pred_hifi_std,
                 resdir=resdir, HP=hp)
