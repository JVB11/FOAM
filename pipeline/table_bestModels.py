"""Write the best models of the grid as a LaTeX table."""
import pandas as pd
import config
################################################################################
merit_abbrev = {'chi2': 'CS', 'mahalanobis': 'MD'}

with open(f'{config.n_sigma_spectrobox}sigmaSpectro_output_tables/bestModel_table_CS.txt', 'w') as outfile:
    outfile.write(r' Grid & Observables & Pattern construction & $M_{ini}$ & $Z_{ini}$ & $\alpha_{\text{CBM}}$ & $\fcbm$ & log($\D[env]$) & $X_c$ & $\chi^2_{\text{red}}$ & MD & AICc($\chi^2_{\text{red}}$) \vspace{1pt} \\'+'\n')
with open(f'{config.n_sigma_spectrobox}sigmaSpectro_output_tables/bestModel_table_MD.txt', 'w') as outfile:
    outfile.write(r' Grid & Observables & Pattern construction & $M_{ini}$ & $Z_{ini}$ & $\alpha_{\text{CBM}}$ & $\fcbm$ & log($\D[env]$) & $X_c$ & $\chi^2_{\text{red}}$ & MD & AICc(MD) \vspace{1pt} \\'+'\n')

best_model_dict = {}
endresult_CS_dict = {}
endresult_MD_dict = {}

# Make a dictionary of the best models for each grid and observable combo, according to each merit function
for pattern in config.pattern_methods:
    for merit in config.merit_functions:
        merit = merit_abbrev[merit]
        for grid in config.grids:
            for obs in config.observable_aic:
                MLE_values_file = f'{config.n_sigma_spectrobox}sigmaSpectro_extracted_freqs/KIC7760680_{grid}_{pattern}_{merit}_{obs}.dat'
                df = pd.read_csv(MLE_values_file, delim_whitespace=True, header=0)
                best_model = df.loc[df['meritValue'].idxmin()]
                best_model_dict.update({f'{grid} {merit} {obs} {pattern}': best_model})

                if merit =='CS':
                    endresult_CS_dict.update({f'{grid} {obs} {pattern} {best_model["M"]} {best_model["Z"]} {best_model["aov"]} {best_model["fov"]} {best_model["logD"]} {best_model["Xc"]}' : {}})
                elif merit =='MD':
                    endresult_MD_dict.update({f'{grid} {obs} {pattern} {best_model["M"]} {best_model["Z"]} {best_model["aov"]} {best_model["fov"]} {best_model["logD"]} {best_model["Xc"]}' : {}})


df_AICc_Chi2 = pd.read_table(f'{config.n_sigma_spectrobox}sigmaSpectro_output_tables/AICc_values_Chi2.tsv', delim_whitespace=True, header=0)
df_AICc_MD   = pd.read_table(f'{config.n_sigma_spectrobox}sigmaSpectro_output_tables/AICc_values_MD.tsv', delim_whitespace=True, header=0)
# Print both the chi2 and MD values of those best models
for merit in config.merit_functions:
    merit = merit_abbrev[merit]
    for grid in config.grids:
        for obs in config.observable_aic:
            for pattern in config.pattern_methods:
                MLE_values_file = f'{config.n_sigma_spectrobox}sigmaSpectro_extracted_freqs/KIC7760680_{grid}_{pattern}_{merit}_{obs}.dat'
                df = pd.read_csv(MLE_values_file, delim_whitespace=True, header=0)
                best_CS = best_model_dict[f'{grid} CS {obs} {pattern}']  # best model according to chi square
                best_MD = best_model_dict[f'{grid} MD {obs} {pattern}']  # best model according to mahalanobis distance

                row_best_CSmodel = df.loc[(df['rot']==best_CS["rot"]) & (df['Z']==best_CS["Z"])
                            & (df['M']==best_CS["M"]) & (df['logD']==best_CS["logD"])
                            & (df['aov']==best_CS["aov"]) & (df['fov']==best_CS["fov"]) & (df['Xc']==best_CS["Xc"])]

                row_best_MDmodel = df.loc[(df['rot']==best_MD["rot"]) & (df['Z']==best_MD["Z"])
                            & (df['M']==best_MD["M"]) & (df['logD']==best_MD["logD"])
                            & (df['aov']==best_MD["aov"]) & (df['fov']==best_MD["fov"]) & (df['Xc']==best_MD["Xc"])]

                if merit == 'CS':   # to get reduced chi2
                    reduced = config.N_dict[obs]-config.k
                else:
                    reduced = 1
                endresult_CS_dict[f'{grid} {obs} {pattern} {best_CS["M"]} {best_CS["Z"]} {best_CS["aov"]} {best_CS["fov"]} {best_CS["logD"]} {best_CS["Xc"]}'].update({f'{merit}' : row_best_CSmodel['meritValue'].iloc[0]/reduced })
                endresult_MD_dict[f'{grid} {obs} {pattern} {best_MD["M"]} {best_MD["Z"]} {best_MD["aov"]} {best_MD["fov"]} {best_MD["logD"]} {best_MD["Xc"]}'].update({f'{merit}' : row_best_MDmodel['meritValue'].iloc[0]/reduced })

                # Get the pre-calculated AICc values from the other file and add them as well
                name = f'{config.star}_{grid}_{pattern}_{merit}_{obs}'
                if merit == 'CS':
                    AICc_CS = df_AICc_Chi2.loc[df_AICc_Chi2.method == name, 'AICc'].values[0]
                    endresult_CS_dict[f'{grid} {obs} {pattern} {best_CS["M"]} {best_CS["Z"]} {best_CS["aov"]} {best_CS["fov"]} {best_CS["logD"]} {best_CS["Xc"]}'].update({f'AICc' : AICc_CS})
                elif merit == 'MD':
                    AICc_MD = df_AICc_MD.loc[df_AICc_MD.method == name, 'AICc'].values[0]
                    endresult_MD_dict[f'{grid} {obs} {pattern} {best_MD["M"]} {best_MD["Z"]} {best_MD["aov"]} {best_MD["fov"]} {best_MD["logD"]} {best_MD["Xc"]}'].update({f'AICc' : AICc_MD})

# Write everything as a LaTeX tables to a file
with open(f'{config.n_sigma_spectrobox}sigmaSpectro_output_tables/bestModel_table_CS.txt', 'a') as outfile:
    for key in sorted(endresult_CS_dict.keys()):
        outfile.write(f'{key.replace(" ", " & ")} & {int(round(endresult_CS_dict[key]["CS"]))} & {int(round(endresult_CS_dict[key]["MD"]))} & {round(endresult_CS_dict[key]["AICc"], 1)} \\\\ \n')

with open(f'{config.n_sigma_spectrobox}sigmaSpectro_output_tables/bestModel_table_MD.txt', 'a') as outfile:
    for key in sorted(endresult_MD_dict.keys()):
        outfile.write(f'{key.replace(" ", " & ")} & {int(round(endresult_MD_dict[key]["CS"]))} & {int(round(endresult_MD_dict[key]["MD"]))} & {round(endresult_MD_dict[key]["AICc"], 1)} \\\\ \n')