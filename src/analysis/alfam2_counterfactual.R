#!/usr/bin/env Rscript
# Real ALFAM2 re-run: (1) reproduce the shipped run, (2) band-application
# counterfactual for the broadcast digestate events (97, 151) under their
# real weather. Parameter set = alfam2pars03 (central), matching 5_run_alfam2.R.

suppressPackageStartupMessages(library(ALFAM2))

INPUT   <- "data/alfam2/alfam2_input.csv"
OUTDIR  <- "results/alfam2_rerun"
dir.create(OUTDIR, showWarnings = FALSE)
PARS    <- alfam2pars03

dat <- read.csv(INPUT, stringsAsFactors = FALSE)
num <- c("ct","TAN.app","app.rate","man.dm","man.ph","air.temp",
         "wind.2m","rain.rate","rain.cum","t.incorp")
for (c in num) dat[[c]] <- suppressWarnings(as.numeric(dat[[c]]))

run <- function(d) {
  res <- ALFAM2::alfam2(d, pars = PARS, app.name = "TAN.app",
                        time.name = "ct", time.incorp = "t.incorp",
                        group = "ID_evenement")
  res <- as.data.frame(res)
  parts <- split(res, res[["ID_evenement"]])
  do.call(rbind, lapply(parts, function(x) {
    r <- x[which.max(x[["ct"]]), , drop = FALSE]
    data.frame(ID_evenement = r[["ID_evenement"]],
               NH3N_kgNha = r[["e"]], er = r[["er"]])
  }))
}

meta <- aggregate(cbind(TAN.app) ~ ID_evenement + Systeme + Categorie + app.mthd,
                  data = dat, FUN = function(x) x[1])

# (1) reproduce original
orig <- run(dat)
orig <- merge(meta, orig, by = "ID_evenement")
orig$pct_TAN <- 100 * orig$NH3N_kgNha / orig$TAN.app
orig <- orig[order(orig$ID_evenement), ]
write.csv(orig, file.path(OUTDIR, "alfam2_original_R.csv"), row.names = FALSE)
cat("\n=== (1) ORIGINAL run (validation) ===\n")
print(orig[, c("ID_evenement","Systeme","Categorie","app.mthd",
               "TAN.app","NH3N_kgNha","pct_TAN")], digits = 5)

# (2) counterfactual: broadcast digestate events -> band (bsth)
cf <- dat
targets <- unique(dat$ID_evenement[dat$app.mthd == "bc" &
                                    dat$Categorie == "Digestat liquide"])
cat("\nCounterfactual targets (bc digestate -> bsth):", targets, "\n")
cf$app.mthd[cf$ID_evenement %in% targets] <- "bsth"
cfres <- run(cf)
cfres <- merge(meta[, c("ID_evenement","Systeme","Categorie","TAN.app")],
               cfres, by = "ID_evenement")
cfres$pct_TAN <- 100 * cfres$NH3N_kgNha / cfres$TAN.app
cfres <- cfres[cfres$ID_evenement %in% targets, ]
write.csv(cfres, file.path(OUTDIR, "alfam2_counterfactual_R.csv"), row.names = FALSE)

cat("\n=== (2) COUNTERFACTUAL: broadcast digestate applied as band ===\n")
comp <- merge(
  orig[orig$ID_evenement %in% targets,
       c("ID_evenement","Systeme","TAN.app","NH3N_kgNha","pct_TAN")],
  cfres[, c("ID_evenement","NH3N_kgNha","pct_TAN")],
  by = "ID_evenement", suffixes = c("_bc","_band"))
comp$avoided_kgNha <- comp$NH3N_kgNha_bc - comp$NH3N_kgNha_band
print(comp, digits = 5)

EF4 <- 0.010; GWP <- 273; R <- 44/28
tot_avoid <- sum(comp$avoided_kgNha)
cat(sprintf("\nBroadcast (as modelled): %.1f kg NH3-N   Band (real re-run): %.1f kg\n",
            sum(comp$NH3N_kgNha_bc), sum(comp$NH3N_kgNha_band)))
cat(sprintf("Avoided: %.1f kg NH3-N  ->  %.0f kg CO2-eq/ha (EF4=%.3f, GWP=%.0f)\n",
            tot_avoid, tot_avoid*EF4*R*GWP, EF4, GWP))
cat(sprintf("  EF4 range 0.002-0.018: %.0f - %.0f kg CO2-eq/ha\n",
            tot_avoid*0.002*R*GWP, tot_avoid*0.018*R*GWP))
