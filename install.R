# R dependencies for the ALFAM2 simulation and counterfactual re-run.
# ALFAM2 is used with parameter set 3 (central). Tested with ALFAM2 4.2.14.
pkgs <- c("Rcpp", "ALFAM2")
new <- pkgs[!(pkgs %in% installed.packages()[, "Package"])]
if (length(new)) install.packages(new, repos = "https://cloud.r-project.org")
# If ALFAM2 is not on your CRAN mirror, install from source:
#   remotes::install_github("AU-BCE-EE/ALFAM2")
cat("ALFAM2", as.character(packageVersion("ALFAM2")), "ready\n")
