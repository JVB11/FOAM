# from foam import build_optimised_pattern as bop
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import astropy.units as u
import multiprocessing, csv, sys
from functools import partial
from pathlib import Path
from lmfit import Minimizer, Parameters
from foam import functions_for_gyre as ffg
import logging

logger = logging.getLogger('logger.bop')
################################################################################
def construct_theoretical_freq_pattern(pulsationGrid_file, observations_file, method_build_series, highest_amplitude_pulsation=[], which_observable='period',
                                        output_file=f'theoretical_frequency_patterns.tsv', asymptotic_object=None, estimated_rotation=None):
    """
    Construct the theoretical frequency pattern for each model in the grid, which correspond to the observed pattern.
    (Each theoretical model is a row in 'pulsationGrid_file'.)
    The rotation rate will be scaled and optimased for each theoretical pattern individually. This optimisation will not be performed if asymptotic_object=None.
    ------- Parameters -------
    pulsationGrid_file: string
        path to file containing input parameters of the models, and the pulsation frequencies of those models
        (as generated by function 'extract_frequency_grid' in 'functions_for_gyre').
    observations_file: string
        Path to the tsv file with observations, with a column for each observable and each set of errors.
        Column names specify the observable, and "_err" suffix denotes that it's the error.
    method_build_series: string
        way to generate the theoretical frequency pattern from each model to match the observed pattern. Options are:
            highest_amplitude: build pattern from the observed highest amplitude    (function 'puls_series_from_given_puls')
            highest_frequency: build pattern from the observed highest frequency    (function 'puls_series_from_given_puls')
            chisq_longest_sequence: build pattern based on longest, best matching sequence of pulsations (function 'chisq_longest_sequence')
    highest_amplitude_pulsation: array of floats
        Only needed if you set method_build_series=highest_amplitude
        Value of the pulsation with the highest amplitude, one for each separated part of the pattern.
        The unit of this value needs to be the same as the observable set through which_observable.
    which_observable: string
        Observable used in the theoretical pattern construction.
    output_file: string
        Name (can include a path) for the file containing all the pulsation frequencies of the grid.
    asymptotic_object: asymptotic (see 'gmode_rotation_scaling')
        Object to calculate g-mode period spacing patterns in the asymptotic regime using the TAR.
    estimated_rotation: float
        Estimation of the rotation rate of the star, used as initial value in the optimisation problem.
    """
    # Read in the files with observed and theoretical frequencies as pandas DataFrames
    Obs_dFrame  = pd.read_table(observations_file, delim_whitespace=True, header=0)
    Theo_dFrame = pd.read_table(pulsationGrid_file, delim_whitespace=True, header=0)

    Obs    = np.asarray(Obs_dFrame[which_observable])
    ObsErr = np.asarray(Obs_dFrame[f'{which_observable}_err'])

    # partial function fixes all parameters of the function except for 1 that is iterated over in the multiprocessing pool.
    theo_pattern_func = partial(theoretical_pattern_from_dfrow, Obs=Obs, ObsErr=ObsErr, which_observable=which_observable,
                                method_build_series=method_build_series, highest_amp_puls=highest_amplitude_pulsation,
                                asymptotic_object=asymptotic_object, estimated_rotation=estimated_rotation)

    # Send the rows of the dataframe iteratively to a pool of processors to get the theoretical pattern for each model
    p = multiprocessing.Pool()
    freqs = p.imap(theo_pattern_func, Theo_dFrame.iterrows())

    # Make the output file directory and write the file
    Path(Path(output_file).parent).mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as tsvfile:
        writer = csv.writer(tsvfile, delimiter='\t')
        header = ['rot', 'rot_err']
        header.extend(list(Theo_dFrame.drop(columns=['rot']).loc[:,:'Xc'].columns))
        for i in range(1, Obs_dFrame.shape[0]+1):
            if i-1 in np.where(Obs_dFrame.index == 'f_missing')[0]:
                f='f_missing'
            else:
                f = 'f'+str(i)
            header.append(f.strip())
        writer.writerow(header)
        for line in freqs:
            writer.writerow(line)
    p.close()

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def theoretical_pattern_from_dfrow(summary_grid_row, Obs, ObsErr, which_observable, method_build_series, highest_amp_puls=[], asymptotic_object=None, estimated_rotation=None):
    """
    Extract model parameters and a theoretical pulsation pattern from a row of the dataFrame that contains all model parameters and pulsation frequencies.
    ------- Parameters -------
    summary_grid_row: tuple, made of (int, pandas series)
        tuple retruned from pandas.iterrows(), first tuple entry is the row index of the pandas dataFrame
        second tuple entry is a pandas series, containing a row from the pandas dataFrame. (This row holds model parameters and pulsation frequencies.)
    Obs: numpy array
        Array of observed frequencies or periods. (Ordered increasing in frequency.)
    ObsErr: numpy array
        Array of errors on the observed frequencies or periods.
    which_observable: string
        Which observables are used in the pattern building, options are 'frequency' or 'period'.
    method_build_series: string
        way to generate the theoretical frequency pattern from each model
        to match the observed pattern. Options are:
            highest_amplitude: build pattern from the observed highest amplitude    (function 'puls_series_from_given_puls')
            highest_frequency: build pattern from the observed highest frequency    (function 'puls_series_from_given_puls')
            chisq_longest_sequence: build pattern based on longest, best matching sequence of pulsations    (function 'chisq_longest_sequence')
    highest_amp_puls: array of floats
        Only needed if you set method_build_series=highest_amplitude
        Value of the pulsation with the highest amplitude, one for each separated part of the pattern.
        The unit of this value needs to be the same as the observable set through which_observable.
    asymptotic_object: asymptotic (see 'gmode_rotation_scaling')
        Object to calculate g-mode period spacing patterns in the asymptotic regime using the TAR.
    estimated_rotation: float
        Estimation of the rotation rate of the star, used as initial value in the optimisation problem.

    ------- Returns -------
    list_out: list
        The input parameters and pulsation frequencies of the theoretical pattern (or periods, depending on 'which_observable').
    """
    freqs = np.asarray(summary_grid_row[1].filter(like='n_pg')) # all keys containing n_pg (these are all the radial orders)
    orders = np.asarray([int(o.replace('n_pg', '')) for o in summary_grid_row[1].filter(like='n_pg').index])    # array with radial orders
    orders=orders[~np.isnan(freqs)]
    freqs=freqs[~np.isnan(freqs)]  # remove all entries that are NaN in the numpy array (for when the models have a different amount of computed modes)

    missing_puls = np.where(Obs==0)[0]          # if frequency was filled in as 0, it indicates an interruption in the pattern
    Obs=Obs[Obs!=0]                             # remove values indicating interruptions in the pattern
    ObsErr=ObsErr[ObsErr!=0]                    # remove values indicating interruptions in the pattern
    missing_puls=[ missing_puls[i]-i for i in range(len(missing_puls)) ]    # Ajust indices for removed 0-values of missing frequencies

    Obs_pattern_parts = np.split(Obs, missing_puls)    # split into different parts of the interrupted pattern
    ObsErr_pattern_parts = np.split(ObsErr, missing_puls)

    if len(Obs_pattern_parts) != len (highest_amp_puls):   # Check if highest_amp_puls has enough entries to not truncate other parts in the zip function.
        if method_build_series == 'highest_amplitude':
            sys.exit(logger.error('Amount of pulsations specified to build patterns from is not equal to the amount of split-off parts in the pattern.'))
        else:   # Content of highest_amp_puls doesn't matter if it's not used to build the pattern.
            highest_amp_puls = [None]*len(Obs_pattern_parts) #We only care about the length if the method doesn't use specified pulsations.

    if asymptotic_object is None: # In this case, rescaling nor optimisation will happen
        residual = rescale_rotation_and_select_theoretical_pattern(None, asymptotic_object, estimated_rotation, freqs, Obs, ObsErr, Obs_pattern_parts,
        ObsErr_pattern_parts, which_observable, method_build_series, highest_amp_puls, False)

        list_out=[estimated_rotation, 0]
        for parameter in summary_grid_row[1][:'Xc'].drop('rot').index:
            list_out.append(summary_grid_row[1][parameter])

        selected_pulsations = Obs + residual
        list_out.extend(selected_pulsations)

    else:
        # Optimise the rotation rate and get the pulsations at that rotation rate
        params = Parameters()
        params.add('rotation', value=estimated_rotation, min=1E-5)

        # Fit rotation to observed pattern with the default leastsq algorithm
        optimise_rotation = Minimizer(rescale_rotation_and_select_theoretical_pattern, params,
                fcn_args=(asymptotic_object, estimated_rotation, freqs, orders, Obs, ObsErr, Obs_pattern_parts,
                ObsErr_pattern_parts, which_observable, method_build_series, highest_amp_puls))

        result_minimizer = optimise_rotation.minimize()
        optimised_pulsations = result_minimizer.residual + Obs
        print(f'chi2: {result_minimizer.chisqr}')
        plot = False
        if result_minimizer.message != 'Fit succeeded.':
            logger.warning(f'Fitting rotation did not succeed: {result_minimizer.message}')
            # print(result_minimizer.nfev)
            # plot = True

        if plot:
            fig1, ax1 = plt.subplots()
            if which_observable == 'frequency':
                Obsperiod = 1/Obs
                optimised_periods = 1/optimised_pulsations
            else:
                Obsperiod = Obs
                optimised_periods = optimised_pulsations
            spacings = ffg.generate_spacing_series(Obsperiod, ObsErr)
            ax1.errorbar(Obsperiod[:-1], spacings[0], fmt='o', yerr=spacings[1], label='obs', color='blue', alpha=0.8)
            ax1.plot(Obsperiod[:-1], spacings[0], color='blue')
            ax1.plot(optimised_periods[:-1], ffg.generate_spacing_series(optimised_periods)[0], '*', ls='solid', color='orange', label = 'optimised')
            ax1.plot(1/freqs[:-1], ffg.generate_spacing_series(1/freqs)[0], '.', ls='solid', label='initial', color='green')

            fig2, ax2 = plt.subplots()

            ax2.errorbar(Obs, Obs, fmt='o', xerr=ObsErr, label='obs', color='blue', alpha=0.8)
            ax2.plot(optimised_periods, optimised_periods, '*', color='orange', label = 'optimised')
            ax2.plot(1/freqs, 1/freqs, '.', label='initial', color='green')

            ax1.legend(prop={'size': 14})
            ax2.legend(prop={'size': 14})
            ax1.set_title(f"initial omega = {estimated_rotation}, optimised omega = {result_minimizer.params['rotation'].value}")
            ax2.set_title(f"initial omega = {estimated_rotation}, optimised omega = {result_minimizer.params['rotation'].value}")
            plt.show()

        # Create list with rotation, its error, all the input parameters, and the optimised pulsations
        list_out=[result_minimizer.params['rotation'].value, result_minimizer.params['rotation'].stderr]
        for parameter in summary_grid_row[1][:'Xc'].drop('rot').index:
            list_out.append(summary_grid_row[1][parameter])
        list_out.extend(optimised_pulsations)

    return list_out

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def rescale_rotation_and_select_theoretical_pattern(params, asymptotic_object, estimated_rotation,
    freqs_input, orders, Obs, ObsErr, Obs_pattern_parts, ObsErr_pattern_parts, which_observable, method_build_series, highest_amp_puls):
    """
    If rotation is not optimised in the modelling, asymptotic_object should be set to 'None' and
    this function will just select a theoretical pulsation pattern based on the specified method.
    If asymptotic_object is supplied, the rotation will be optimised and this will be the
    objective function for the lmfit Minimizer class to minimise the output of.
    Rescales the theoretical pulsation pattern using the asymptotic object from
    'gmode_rotation_scaling', and selects a theoretical pulsation pattern based
    on the specified method.

    ------- Parameters -------
    params: Parameter (object of lmfit)
        The paramter used to optimise the fit. In this case rotation in units of 1/day.
    asymptotic_object: asymptotic (see 'gmode_rotation_scaling')
        Object to calculate g-mode period spacing patterns in the asymptotic regime using the TAR.
    estimated_rotation: float
        Estimated rotation rate in units of 1/day. Used as initial value in the optimisation problem.
    freqs_input: numpy array
        Array of the frequencies as computed by GYRE, to be scaled to the optimal rotation rate.
    orders: numpy array
        Array with the radial orders of the theoretical input frequencies.
    Obs: numpy array
        Array of observed frequencies or periods. (Ordered increasing in frequency.)
    ObsErr: numpy array
        Array of errors on the observed frequencies or periods.
    Obs_pattern_parts, ObsErr_pattern_parts: list of numpy arrays
        Holds a numpy array per split off part of the observerd pattern if it is interrupted.
        The list contains only one array if the observed pattern is uninterrupted.
    which_observable: string
        Which observables are used in the pattern building, options are 'frequency' or 'period'.
    method_build_series: string
        way to generate the theoretical frequency pattern from each model
        to match the observed pattern. Options are:
            highest_amplitude: build pattern from the observed highest amplitude    (function 'puls_series_from_given_puls')
            highest_frequency: build pattern from the observed highest frequency    (function 'puls_series_from_given_puls')
            chisq_longest_sequence: build pattern based on longest, best matching sequence of pulsations    (function 'chisq_longest_sequence')
    highest_amp_puls: array of floats
        Only needed if you set method_build_series=highest_amplitude
        Value of the pulsation with the highest amplitude, one for each separated part of the pattern.
        The unit of this value needs to be the same as the observable set through which_observable.

    ------- Returns -------
    output_pulsations - Obs: numpy array
        Differences between the scaled pulsations and the observations.
        The array to be minimised by the lmfit Minimizer if rotation is opitmised.
    """
    if asymptotic_object is not None:
        v = params.valuesdict()
        if estimated_rotation ==0:  # To avoid division by zero in scale_pattern
            estimated_rotation=1E-99
        freqs = asymptotic_object.scale_pattern(freqs_input/u.d, estimated_rotation/u.d, v['rotation']/u.d) *u.d
    else:
        freqs = freqs_input

    periods = 1/freqs

    output_pulsations = []
    for Obs_part, ObsErr_part, highest_amp_puls_part in zip(Obs_pattern_parts, ObsErr_pattern_parts, highest_amp_puls):
        if len(output_pulsations)>0: output_pulsations.append(0)  # To indicate interruptions in the pattern

        if which_observable=='frequency':
            # remove frequencies that were already chosen in a different, split-off part of the pattern
            if len(output_pulsations)>0:
                if orders[1]==orders[0]-1:  # If input is in increasing radial order (decerasing n_pg, since n_pg is negative for g-modes)
                    np.delete(freqs, np.where(freqs>=output_pulsations[-2])) #index -2 to get lowest, non-zero freq
                else:                       # If input is in decreasing radial order
                    np.delete(freqs, np.where(freqs<=max(output_pulsations)))
            Theo_value = freqs
            ObsPeriod = 1/Obs_part
            ObsErr_P = ObsErr_part/Obs_part**2
            highest_obs_freq = max(Obs_part)

        elif which_observable=='period':
            # remove periods that were already chosen in a different, split-off part of the pattern
            if len(output_pulsations)>0:
                if orders[1]==orders[0]-1:  # If input is in increasing radial order (decerasing n_pg, since n_pg is negative for g-modes)
                    np.delete(periods, np.where(periods<=max(output_pulsations)))
                else:                       # If input is in decreasing radial order
                    np.delete(periods, np.where(periods>=output_pulsations[-2])) #index -2 to get lowest, non-zero period
            Theo_value = periods
            ObsPeriod = Obs_part
            ObsErr_P = ObsErr_part
            highest_obs_freq = min(Obs_part)  # highest frequency is lowest period
        else:
            sys.exit(logger.error('Unknown observable to fit'))

        if method_build_series == 'highest_amplitude':
            selected_theoretical_pulsations = puls_series_from_given_puls(Theo_value, Obs_part, highest_amp_puls_part)
        elif method_build_series == 'highest_frequency':
            selected_theoretical_pulsations = puls_series_from_given_puls(Theo_value, Obs_part, highest_obs_freq)
        elif method_build_series == 'chisq_longest_sequence':
            series_chi2,final_theoretical_periods,corresponding_orders = chisq_longest_sequence(periods,orders,ObsPeriod,ObsErr_P, plot=False)
            if which_observable=='frequency':
                selected_theoretical_pulsations = 1/np.asarray(final_theoretical_periods)
            elif which_observable=='period':
                selected_theoretical_pulsations = final_theoretical_periods
        else:
            sys.exit(logger.error('Incorrect method to build pulsational series.'))

        output_pulsations.extend(selected_theoretical_pulsations)

    return (output_pulsations - Obs)

################################################################################
def puls_series_from_given_puls(TheoIn, Obs, Obs_to_build_from, plot=False):
    """
    Generate a theoretical pulsation pattern (can be in frequency or period) from the given observations.
    Build consecutively in radial order, starting from the theoretical value closest to the provided observational value.
    ------- Parameters -------
    TheoIn: numpy array

        Array of theoretical frequencies or periods.
    Obs: numpy array
        Array of observed frequencies or periods.
    Obs_to_build_from: float
        Observed frequency or period value to start building the pattern from.
    plot: boolean
        Make a period spacing diagram for the constructed series.

    ------- Returns -------
    Theo_sequence: list of float
        The constructed theoretical frequency pattern
    """
    nth_obs = np.where(Obs==Obs_to_build_from)[0][0]    # get index of observation to build the series from
    diff = abs(TheoIn - Obs_to_build_from)    # search theoretical freq closest to the given observed one
    index = np.where(diff==min(diff))[0][0]   # get index of this theoretical frequency

    # Insert a value of -1 if observations miss a theoretical counterpart in the begining
    Theo_sequence = []
    if (index-nth_obs)<0:
        for i in range(abs((index-nth_obs))):
            Theo_sequence.append(-1)
        Theo_sequence.extend(TheoIn[0:index+(len(Obs)-nth_obs)])
    else:
        Theo_sequence.extend(TheoIn[index-nth_obs:index+(len(Obs)-nth_obs)])

    # Insert a value of -1 if observations miss a theoretical counterpart at the end
    if( index+(len(Obs)-nth_obs) > len(TheoIn)):
        for i in range((index+(len(Obs)-nth_obs)) - len(TheoIn)):
            Theo_sequence.append(-1)

    if plot is True:
        fig=plt.figure()
        ax = fig.add_subplot(111)
        Theo = np.asarray(Theo_sequence)
        ax.plot((1/Obs)[::-1][:-1],np.diff((1/Obs)[::-1])*86400,'ko',lw=1.5,linestyle='-')
        ax.plot((1./Theo)[::-1][:-1], -np.diff(1./Theo)[::-1]*86400, 'ko', color='blue', lw=1.5,linestyle='--', markersize=6, markeredgewidth=0.,)
        plt.show()    # print(GLOBAL_PULSATION)


    return Theo_sequence

################################################################################
################################################################################
# Function adapted from Cole Johnston
################################################################################
def chisq_longest_sequence(tperiods,orders,operiods,operiods_errors, plot=False):
    """
    Method to extract the theoretical pattern that best matches the observed one.
    Match each observed mode period to its best matching theoretical counterpart,
    and adopt the longest sequence of consecutive modes found this way.
    In case of multiple mode series with the same length, a final pattern selection
    is made based on the best (chi-square) match between theory and observations.
    ------- Parameters -------
    tperiods, orders : list of floats, integers
        theroretical periods and their radial orders
    operiods, operiods_errors : list of floats
        observational periods and their errors

    ------- Returns -------
    series_chi2: float
        chi2 value of the selected theoretical frequencies
    final_theoretical_periods: numpy array of floats
        the selected theoretical periods that best match the observed pattern
    corresponding_orders: list of integers
        the radial orders of the returned theoretical periods
    """
    if len(tperiods)<len(operiods):
        return 1e16, [-1. for i in range(len(operiods))], [-1 for i in range(len(operiods))]
    else:
        # Find the best matches per observed period
        pairs_orders = []
        for ii,period in enumerate(operiods):
            ## Chi_squared array definition
            chisqs = np.array([ ( (period-tperiod)/operiods_errors[ii] )**2 for tperiod in tperiods  ])

            ## Locate the theoretical frequency (and accompanying order) with the best chi2
            min_ind = np.where( chisqs == min( chisqs ) )[0]
            best_match = tperiods[min_ind][0]
            best_order = orders[min_ind][0]

            ## Toss everything together for bookkeeping
            pairs_orders.append([period,best_match,int(best_order),chisqs[min_ind][0]])

        pairs_orders = np.array(pairs_orders)
        if plot is True:
            # Plot the results
            plt.figure(1,figsize=(6.6957,6.6957))
            plt.subplot(211)
            plt.plot(pairs_orders[:,0],pairs_orders[:,1],'o')
            plt.ylabel('$\\mathrm{Period \\,[d]}$',fontsize=20)
            plt.subplot(212)
            plt.plot(pairs_orders[:,0],pairs_orders[:,2],'o')
            plt.ylabel('$\\mathrm{Radial \\, Order}$',fontsize=20)
            plt.xlabel('$\\mathrm{Period \\,[d]}$',fontsize=20)

        if orders[1]==orders[0]-1:  # If input is in increasing radial order (decerasing n_pg, since n_pg is negative for g-modes)
            increase_or_decrease=-1
        else:                       # If input is in decreasing radial order
            increase_or_decrease=1

        sequences = []
        ## Go through all pairs of obs and theoretical frequencies and
        ## check if the next observed freqency has a corresponding theoretical frequency
        ## with the consecutive radial order.
        current = []
        lp = len(pairs_orders[:-1])
        for ii,sett in enumerate(pairs_orders[:-1]):
            if abs(sett[2]) == abs(pairs_orders[ii+1][2])+increase_or_decrease:
                current.append(sett)
            else:   # If not consecutive radial order, save the current sequence and start a new one.
               	current.append(sett)
                sequences.append(np.array(current).reshape(len(current),4))
                current = []
            if (ii==lp-1):
                current.append(sett)
                sequences.append(np.array(current).reshape(len(current),4))
                current = []
        len_list = np.array([len(x) for x in sequences])
        longest = np.where(len_list == max(len_list))[0]

        ## Test if there really is one longest sequence
        if len(longest) == 1:
            lseq = sequences[longest[0]]

        ## if not, pick, of all the sequences with the same length, the best based on chi2
        else:
            scores = [ np.sum(sequences[ii][:,-1])/len(sequences[ii]) for  ii in longest]
            min_score = np.where(scores == min(scores))[0][0]
            lseq = sequences[longest[min_score]]

        obs_ordering_ind = np.where(operiods == lseq[:,0][0])[0][0]
        thr_ordering_ind = np.where(tperiods == lseq[:,1][0])[0][0]

        ordered_theoretical_periods   = []
        corresponding_orders          = []

        thr_ind_start = thr_ordering_ind - obs_ordering_ind
        thr_ind_current = thr_ind_start

        for i,oper in enumerate(operiods):
            thr_ind_current = thr_ind_start + i
            if (thr_ind_current < 0):
                tper = -1
                ordr = -1
            elif (thr_ind_current >= len(tperiods)):
                tper = -1
                ordr = -1
            else:
                tper = tperiods[thr_ind_current]
                ordr = orders[thr_ind_current]
            ordered_theoretical_periods.append(tper)
            corresponding_orders.append(ordr)

        #final_theoretical_periods = np.sort(np.hstack([ordered_theoretical_periods_a,ordered_theoretical_periods_b]))[::-1]
        final_theoretical_periods = np.array(ordered_theoretical_periods)

        obs_series,obs_series_errors = ffg.generate_spacing_series(operiods,operiods_errors)
        thr_series, _ = ffg.generate_spacing_series(final_theoretical_periods)

        obs_series        = np.array(obs_series)
        obs_series_errors = np.array(obs_series_errors)
        thr_series        = np.array(thr_series)

        series_chi2 = np.sum( ( (obs_series-thr_series) /obs_series_errors )**2 ) / len(obs_series)

        if plot is True:
            fig = plt.figure(2,figsize=(6.6957,6.6957))
            fig.suptitle('$\mathrm{Longest \\ Sequence}$',fontsize=20)
            axT = fig.add_subplot(211)
            # axT.errorbar(operiods[1:],obs_series,yerr=obs_series_errors,marker='x',color='black',label='Obs')
            # axT.plot(final_theoretical_periods[1:],thr_series,'rx-',label='Theory')
            axT.errorbar(list(range(len(obs_series))),obs_series,yerr=obs_series_errors,marker='x',color='black',label='Obs')
            axT.plot(list(range(len(thr_series))),thr_series,'rx-',label='Theory')
            axT.set_ylabel('$\mathrm{Period \\ Spacing \\ (s)}$',fontsize=20)
            axT.legend(loc='best')
            axB = fig.add_subplot(212)
            axB.errorbar(operiods[1:],obs_series-thr_series,yerr=obs_series_errors,marker='',color='black')
            axB.set_ylabel('$\mathrm{Residuals \\ (s)}$',fontsize=20)
            axB.set_xlabel('$\mathrm{Period \\ (d^{-1})}$',fontsize=20)
            axB.text(0.75,0.85,'$\chi^2 = %.2f$'%series_chi2,fontsize=15,transform=axB.transAxes)

            plt.show()

        return series_chi2,final_theoretical_periods,corresponding_orders
