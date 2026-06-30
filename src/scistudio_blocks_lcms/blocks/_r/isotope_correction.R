#!/usr/bin/env Rscript
# Natural isotope abundance correction for LCMS feature tables.
#
# Embedded by scistudio_package_lcms.blocks.isotope_correction.IsotopeCorrection.
# The Python block writes the feature table to a CSV, sets the parameters below
# via environment variables, and runs this script with Rscript; this script runs
# AccuCor (single-isotope) or AccuCor2 (dual-isotope) and writes the four output
# matrices (Original, Corrected, Normalized, Pool size) back as CSVs the block
# reads onto its four output ports.
#
# Python <-> R exchange is CSV (SciStudio's R interchange convention); any Excel
# the R packages require is written here, inside R.
#
# Environment contract (all paths absolute):
#   ACCUCOR_MODE            "accucor" | "accucor2"
#   ACCUCOR_INPUT           input feature-table CSV
#   ACCUCOR_OUTPUT_DIR      dir to write original.csv/corrected.csv/normalized.csv/pool.csv
#   ACCUCOR_WORKDIR         scratch dir for intermediate files
#   ACCUCOR_SAMPLE_COLUMNS  comma-separated sample (intensity) column names
#   ACCUCOR_RESOLUTION      MS resolution (numeric)
#   ACCUCOR_RES_DEFINED_AT  m/z the resolution is defined at (numeric, default 200)
#   ACCUCOR_C13_PURITY      tracer 13C purity (numeric, optional)
#   ACCUCOR_H2N15_PURITY    tracer 2H/15N purity for AccuCor2 (numeric, optional)
#   ACCUCOR_LABEL           AccuCor2 label elements, e.g. "CH" or "CN"
#   ACCUCOR_CHARGE          ion charge for the AccuCor2 formula list (int, default -1)

`%||%` <- function(x, y) if (is.null(x) || is.na(x) || !nzchar(x)) y else x

env_num <- function(name, default = NA_real_) {
  raw <- Sys.getenv(name)
  if (!nzchar(raw)) default else as.numeric(raw)
}

main <- function() {
  mode <- Sys.getenv("ACCUCOR_MODE")
  input <- Sys.getenv("ACCUCOR_INPUT")
  outdir <- Sys.getenv("ACCUCOR_OUTPUT_DIR")
  workdir <- Sys.getenv("ACCUCOR_WORKDIR") %||% outdir
  sample_cols <- strsplit(Sys.getenv("ACCUCOR_SAMPLE_COLUMNS"), ",", fixed = TRUE)[[1]]
  resolution <- env_num("ACCUCOR_RESOLUTION")
  res_defined_at <- env_num("ACCUCOR_RES_DEFINED_AT", 200)

  if (is.na(resolution)) stop("ACCUCOR_RESOLUTION is required")
  dir.create(outdir, recursive = TRUE, showWarnings = FALSE)

  # Write one result matrix to <outdir>/<name>.csv; an absent element writes an
  # empty frame so the Python side still gets a (possibly empty) port output.
  write_out <- function(x, name) {
    path <- file.path(outdir, paste0(name, ".csv"))
    if (is.null(x)) x <- data.frame()
    utils::write.csv(x, path, row.names = FALSE)
  }

  df <- utils::read.csv(input, check.names = FALSE, stringsAsFactors = FALSE)

  if (identical(mode, "accucor")) {
    if (!requireNamespace("accucor", quietly = TRUE)) {
      stop("R package 'accucor' is not installed (devtools::install_github('XiaoyangSu/AccuCor'))")
    }
    # AccuCor treats every column not named compound/formula/isotopeLabel as a
    # sample, so drop the other El-MAVEN annotation columns first.
    keep <- intersect(c("compound", "formula", "isotopeLabel", sample_cols), names(df))
    sub <- df[, keep, drop = FALSE]

    args <- list(
      data = sub,
      resolution = resolution,
      resolution_defined_at = res_defined_at,
      report_pool_size_before_df = TRUE
    )
    c13_purity <- env_num("ACCUCOR_C13_PURITY")
    if (!is.na(c13_purity)) args$purity <- c13_purity

    result <- do.call(accucor::natural_abundance_correction, args)
    write_out(result$Original, "original")
    write_out(result$Corrected, "corrected")
    write_out(result$Normalized, "normalized")
    write_out(result$PoolAfterDF, "pool")
  } else if (identical(mode, "accucor2")) {
    if (!requireNamespace("accucor2", quietly = TRUE)) {
      stop("R package 'accucor2' is not installed (devtools::install_github('wangyujue23/AccuCor2'))")
    }
    for (pkg in c("dplyr", "tidyr", "stringr", "openxlsx")) {
      if (!requireNamespace(pkg, quietly = TRUE)) stop(sprintf("R package '%s' is required for AccuCor2", pkg))
    }
    library(dplyr); library(stringr)

    charge <- as.integer(env_num("ACCUCOR_CHARGE", -1))
    label <- Sys.getenv("ACCUCOR_LABEL") %||% "CH"

    # Reshape El-MAVEN isotopeLabel into the AccuCor2 13C#/2H# layout
    # (transcribed from the reference flux pipeline's R Markdown).
    clean <- df %>%
      mutate(.iso = case_when(
        grepl("PARENT", isotopeLabel) ~ "0-0",
        grepl("^D2", isotopeLabel) ~ paste0("0-", str_extract(isotopeLabel, "[0-9]+$")),
        grepl("D2", isotopeLabel) ~ str_extract(isotopeLabel, "[0-9]+\\-[0-9]+$"),
        TRUE ~ paste0(str_extract(isotopeLabel, "[0-9]+$"), "-0")
      )) %>%
      mutate(
        `13C#` = as.numeric(str_extract(.iso, "^[0-9]+")),
        `2H#` = as.numeric(str_extract(.iso, "[0-9]+$")),
        `Expected?` = 1
      ) %>%
      select(compound, `13C#`, `2H#`, `Expected?`, all_of(sample_cols))

    input_xlsx <- file.path(workdir, "input_for_accucor2.xlsx")
    openxlsx::write.xlsx(clean, input_xlsx, sheetName = "Sheet 1")

    metabolites <- df %>%
      select(compound, formula) %>%
      mutate(charge = charge) %>%
      distinct()
    metab_csv <- file.path(workdir, "formula_list.csv")
    utils::write.table(metabolites, metab_csv, sep = ",", row.names = FALSE, quote = FALSE)

    args <- list(input_xlsx, "Sheet 1", metab_csv, label, Resolution = resolution)
    c13_purity <- env_num("ACCUCOR_C13_PURITY")
    h2n15_purity <- env_num("ACCUCOR_H2N15_PURITY")
    if (!is.na(c13_purity)) args$C13Purity <- c13_purity
    if (!is.na(h2n15_purity)) args$H2N15Purity <- h2n15_purity

    result <- do.call(accucor2::dual_correction, args)
    write_out(result$Original, "original")
    write_out(result$Corrected, "corrected")
    write_out(result$Normalized, "normalized")
    write_out(result[["Pool size"]], "pool")
  } else {
    stop(sprintf("unknown ACCUCOR_MODE: %s", mode))
  }
}

main()
