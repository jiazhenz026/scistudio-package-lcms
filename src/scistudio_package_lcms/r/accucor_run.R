#!/usr/bin/env Rscript
# Bundled wrapper that drives AccuCor (single isotope) and AccuCor2 (dual
# isotope) natural-abundance correction for the SciStudio LCMS package.
#
# This script is a fixed, package-owned interface — it is NOT user-editable.
# The Python IsotopeCorrection block prepares the inputs, invokes this script,
# and reads the outputs back; see blocks/isotope_correction.py.
#
# Usage:
#   Rscript accucor_run.R <exchange_dir> <mode> <resolution> <res_def_at> \
#                         <purity_c13> <purity_h2n15>
#
# Inputs in <exchange_dir>:
#   input.xlsx   - single: verbatim El-MAVEN table (Compound/Formula/IsotopeLabel + samples)
#                  dual:   prepared table (Compound, parent, 13C#, 2H#, Expected?, samples)
#   formula.csv  - dual only: compoundId, formula, charge
#
# Outputs written to <exchange_dir>:
#   corrected.csv  - natural-abundance-corrected isotopologue intensities
#   mid.csv        - normalised mass isotopologue distribution (fractional)
#   pool_size.csv  - total pool size per compound

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 6) {
  stop("accucor_run.R: expected 6 args (exchange_dir mode resolution res_def_at purity_c13 purity_h2n15)")
}
exchange_dir <- args[[1]]
mode <- args[[2]]
resolution <- as.numeric(args[[3]])
res_def_at <- as.numeric(args[[4]])
purity_c13 <- as.numeric(args[[5]])
purity_h2n15 <- as.numeric(args[[6]])

setwd(exchange_dir)
input_xlsx <- file.path(exchange_dir, "input.xlsx")

write_out <- function(corrected, normalized, pool) {
  write.csv(corrected, file.path(exchange_dir, "corrected.csv"), row.names = FALSE)
  write.csv(normalized, file.path(exchange_dir, "mid.csv"), row.names = FALSE)
  write.csv(pool, file.path(exchange_dir, "pool_size.csv"), row.names = FALSE)
}

if (identical(mode, "single")) {
  suppressMessages(library(accucor))
  res <- accucor::natural_abundance_correction(
    path = input_xlsx,
    sheet = 1,
    resolution = resolution,
    resolution_defined_at = res_def_at,
    purity = if (is.na(purity_c13)) NULL else purity_c13,
    report_pool_size_before_df = FALSE
  )
  write_out(res[["Corrected"]], res[["Normalized"]], res[["PoolAfterDF"]])
} else if (identical(mode, "dual")) {
  suppressMessages(library(accucor2))
  formula_csv <- file.path(exchange_dir, "formula.csv")
  res <- accucor2::dual_correction(
    InputFile = input_xlsx,
    InputSheetName = "Sheet 1",
    MetaboliteListName = formula_csv,
    Isotopes = "CH",
    Resolution = resolution,
    ResDefAt = res_def_at,
    C13Purity = purity_c13,
    H2N15Purity = purity_h2n15,
    ReportPoolSize = TRUE
  )
  write_out(res[["Corrected"]], res[["Normalized"]], res[["Pool size"]])
} else {
  stop(sprintf("accucor_run.R: unknown mode '%s' (expected 'single' or 'dual')", mode))
}
