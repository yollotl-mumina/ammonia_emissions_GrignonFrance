#!/usr/bin/env Rscript
# =============================================================================
# run_alfam2.R
# -----------------------------------------------------------------------------
# Run the official ALFAM2 model (CRAN package "ALFAM2") on each Trajectoire
# ALFAM2 hourly input file:
#
#   * ALFAM2_entrada_horaria.xlsx   (full set, 2018-2025)
#   * ALFAM2_first_rotation.xlsx    (rotation 1)
#   * ALFAM2_second_rotation.xlsx   (rotation 2, COM/LOM)
#
# ALFAM2 (Hafner et al.) is a forward model: it PREDICTS the cumulative NH3
# emission from liquid organic effluents along the hourly series. The input
# file is in long format (one row per event x hour), grouped by ID_evenement
# with time index ct (hours since application).
#
# For each input file the script writes, to OUTPUT_DIR:
#   <stem>_alfam2_hourly.csv    full series with the predicted emission columns
#   <stem>_alfam2_by_event.csv  one row per event: final cumulative emission
#
# Output columns from ALFAM2:
#   e   = cumulative NH3-N emission (kg N/ha, same units as TAN.app)
#   er  = e relative to applied TAN (fraction; x100 = % of TAN volatilised)
#
# NOTE ON UNITS / PARAMETERS:
#   Parameter set = pars03 (central estimates). Calibration domain: wind 0-10
#   m/s, air temp 0-30 C, rain rate 0-2.5 mm/h. Some events extrapolate beyond
#   this; treat their predictions with caution (flagged in the input "Notas").
#
# All comments are ASCII only (avoids the encoding errors seen previously).
# Input files are never modified.
#
# Author: Daniela Zuniga-Jimenez - AgroParisTech / UMR ECOSYS - 2026
# =============================================================================

suppressPackageStartupMessages({
  ok_alfam2 <- requireNamespace("ALFAM2", quietly = TRUE)
  ok_readxl <- requireNamespace("readxl", quietly = TRUE)
})
if (!ok_alfam2 || !ok_readxl) {
  stop(paste0(
    "Missing R package(s). Install them first:\n",
    "  install.packages(c(\"ALFAM2\", \"readxl\"))\n"
  ))
}
library(ALFAM2)
library(readxl)

# -----------------------------------------------------------------------------
# CONFIGURATION  -- edit only this block
# -----------------------------------------------------------------------------
# Use forward slashes (R accepts them on Windows).
INPUTS <- c(
  "C:/Users/dzuni/OneDrive/Documentos/INTERNSHIP/ALFAM2_entrada_horaria.xlsx",
  "C:/Users/dzuni/OneDrive/Documentos/INTERNSHIP/Resultats_FINALES/ALFAM2_first_rotation.xlsx",
  "C:/Users/dzuni/OneDrive/Documentos/INTERNSHIP/Resultats_FINALES/ALFAM2_second_rotation.xlsx"
)
SHEET      <- "ALFAM2_horario"
OUTPUT_DIR <- "C:/Users/dzuni/OneDrive/Documentos/INTERNSHIP/Resultats_FINALES"

# ALFAM2 column roles (must match the headers in the input file).
APP_NAME    <- "TAN.app"       # applied TAN (kg N/ha)
TIME_NAME   <- "ct"            # hours since application
TIME_INCORP <- "t.incorp"     # incorporation delay (h); NA where incorp == none
GROUP       <- "ID_evenement"  # event grouping key

# Predictor columns expected by the model (checked before running).
REQUIRED <- c("ID_evenement", "ct", "TAN.app", "app.rate", "app.mthd",
              "man.dm", "man.ph", "man.source", "air.temp", "wind.2m",
              "rain.rate", "rain.cum", "incorp", "t.incorp")

# -----------------------------------------------------------------------------
# Resolve the parameter set (pars03). Object name has varied across versions,
# so try the known spellings and fail clearly if none is found.
# -----------------------------------------------------------------------------
resolve_pars <- function() {
  for (nm in c("ALFAM2pars03", "alfam2pars03", "pars03")) {
    if (exists(nm, where = asNamespace("ALFAM2"), inherits = FALSE)) {
      return(get(nm, envir = asNamespace("ALFAM2")))
    }
    if (exists(nm)) return(get(nm))
  }
  stop("Could not find the pars03 parameter object in the ALFAM2 package. ",
       "Check `?alfam2` and set PARS manually.")
}
PARS <- resolve_pars()

# -----------------------------------------------------------------------------
# Load one workbook and validate the required ALFAM2 columns.
# -----------------------------------------------------------------------------
load_alfam2 <- function(path) {
  if (!file.exists(path)) {
    stop(sprintf("Input file not found:\n  %s", path))
  }
  sheets <- readxl::excel_sheets(path)
  sheet  <- if (SHEET %in% sheets) SHEET else sheets[[1]]
  dat <- as.data.frame(readxl::read_excel(path, sheet = sheet))

  missing <- setdiff(REQUIRED, names(dat))
  if (length(missing) > 0) {
    stop(sprintf("%s: missing ALFAM2 column(s): %s",
                 basename(path), paste(missing, collapse = ", ")))
  }

  # ALFAM2 needs numeric predictors; coerce defensively (commas already absent).
  num_cols <- c("ct", "TAN.app", "app.rate", "man.dm", "man.ph",
                "air.temp", "wind.2m", "rain.rate", "rain.cum", "t.incorp")
  for (col in num_cols) dat[[col]] <- suppressWarnings(as.numeric(dat[[col]]))

  message(sprintf("  Loaded %d rows / %d events from '%s' (sheet '%s').",
                  nrow(dat), length(unique(dat[[GROUP]])),
                  basename(path), sheet))
  dat
}

# -----------------------------------------------------------------------------
# Run ALFAM2 on one data frame and return the hourly series with predictions.
# -----------------------------------------------------------------------------
run_model <- function(dat) {
  # Only pass exactly-named formal arguments. Optional flags (prep/check/warn)
  # are left at their defaults: their abbreviations partial-match more than one
  # formal in some package versions ("argument matches multiple formal
  # arguments"), so passing them explicitly is what triggered that error.
  res <- ALFAM2::alfam2(
    dat,
    pars        = PARS,
    app.name    = APP_NAME,
    time.name   = TIME_NAME,
    time.incorp = TIME_INCORP,
    group       = GROUP
  )
  as.data.frame(res)
}

# -----------------------------------------------------------------------------
# Collapse the hourly series to one final cumulative value per event.
# The model output (res) keeps the predictors and predictions but DROPS the
# descriptive columns (Systeme, Categorie, Date, app.mthd). So the final
# emission is taken from res, and the event metadata is merged back from the
# original input (dat), by ID_evenement.
# -----------------------------------------------------------------------------
summarise_by_event <- function(res, dat) {
  # Identify the cumulative-emission column (standard name is "e").
  emis_col <- intersect(c("e", "emis", "cum.emis"), names(res))[1]
  rel_col  <- intersect(c("er", "e.rel"), names(res))[1]
  if (is.na(emis_col)) {
    stop("ALFAM2 output has no cumulative-emission column ('e'). ",
         "Inspect names(res) and adjust summarise_by_event().")
  }

  # Final cumulative emission per event = row at the maximum ct in each group.
  parts <- split(res, res[[GROUP]])
  finals <- do.call(rbind, lapply(parts, function(d) {
    r <- d[which.max(d[[TIME_NAME]]), , drop = FALSE]
    data.frame(
      ID_evenement = r[[GROUP]],
      NH3N_kgNha   = r[[emis_col]],
      er           = if (!is.na(rel_col)) r[[rel_col]] else NA_real_,
      stringsAsFactors = FALSE
    )
  }))

  # Event-level metadata from the ORIGINAL input (one row per event).
  meta_parts <- split(dat, dat[[GROUP]])
  meta <- do.call(rbind, lapply(meta_parts, function(d) {
    r <- d[1, , drop = FALSE]
    data.frame(
      ID_evenement  = r[[GROUP]],
      Systeme       = r[["Systeme"]],
      Categorie     = r[["Categorie"]],
      Date          = as.character(r[["Date"]]),
      app_mthd      = r[["app.mthd"]],
      TAN_app_kgNha = r[[APP_NAME]],
      stringsAsFactors = FALSE
    )
  }))

  out <- merge(meta, finals, by = "ID_evenement")
  # Emission as % of applied TAN (prefer the model's relative column).
  out$emis_pct_TAN <- ifelse(!is.na(out$er),
                             100 * out$er,
                             100 * out$NH3N_kgNha / out$TAN_app_kgNha)
  out$er <- NULL
  out <- out[order(out$Date, out$ID_evenement), ]
  rownames(out) <- NULL
  out
}

# -----------------------------------------------------------------------------
# Process one input file end to end.
# -----------------------------------------------------------------------------
process_file <- function(path) {
  message(sprintf("Processing %s", basename(path)))
  dat <- load_alfam2(path)
  res <- run_model(dat)
  by_event <- summarise_by_event(res, dat)

  # Enrich the hourly output with the descriptive columns the model dropped,
  # so the CSV is self-contained (merge by event; res keeps ID_evenement).
  meta_cols  <- intersect(c("ID_evenement", "Systeme", "Categorie", "Date",
                            "app.mthd"), names(dat))
  meta_event <- dat[!duplicated(dat[[GROUP]]), meta_cols, drop = FALSE]
  res_out    <- merge(meta_event, res, by = "ID_evenement",
                      suffixes = c("", ".dup"))

  if (!dir.exists(OUTPUT_DIR)) dir.create(OUTPUT_DIR, recursive = TRUE)
  stem <- tools::file_path_sans_ext(basename(path))
  f_hourly <- file.path(OUTPUT_DIR, paste0(stem, "_alfam2_hourly.csv"))
  f_event  <- file.path(OUTPUT_DIR, paste0(stem, "_alfam2_by_event.csv"))

  write.csv(res_out,  f_hourly, row.names = FALSE)
  write.csv(by_event, f_event,  row.names = FALSE)

  total <- sum(by_event$NH3N_kgNha, na.rm = TRUE)
  message(sprintf("  Total NH3-N: %.2f kg/ha across %d events.",
                  total, nrow(by_event)))
  message(sprintf("  Wrote: %s", basename(f_hourly)))
  message(sprintf("  Wrote: %s", basename(f_event)))
}

# -----------------------------------------------------------------------------
# Main: loop over the three files, isolating per-file failures.
# -----------------------------------------------------------------------------
main <- function() {
  failures <- 0L
  for (path in INPUTS) {
    res <- tryCatch(process_file(path), error = function(e) {
      message(sprintf("ERROR (%s): %s", basename(path), conditionMessage(e)))
      failures <<- failures + 1L
      invisible(NULL)
    })
  }
  if (failures > 0L) {
    message(sprintf("Finished with %d file(s) failed.", failures))
    quit(status = 1L)
  }
  message("All files processed.")
}

main()
