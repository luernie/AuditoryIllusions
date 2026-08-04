# ============================================================
# analysis.R
# Two-Way Repeated Measures ANOVA
# Auditory Illusions Experiment — Risset & Shepard
# ============================================================
# Factors:
#   Modality (3 levels): audio, haptic, both
#   Stimulus (7 levels): filenames
# Run separately for 4 datasets:
#   risset_ranking, risset_flashcards,
#   shepard_ranking, shepard_flashcards
# ============================================================

# install.packages(c("tidyverse", "rstatix", "ggpubr"))
library(tidyverse)
library(rstatix)
library(ggpubr)

# ============================================================
# PATHS — edit here
# ============================================================

root_path   <- "C:/Users/luern/Documents/CodingProjects/AuditoryIllusions/analysis/output/"
results_dir <- paste0(root_path, "anova_results/")
if (!dir.exists(results_dir)) dir.create(results_dir, recursive = TRUE)

# ============================================================
# ILLUSION STIMULI
# Used for the planned haptic vs audio transfer contrast
# ============================================================

ILLUSION_STIMULI <- list(
  risset  = c("risset_accelerating_haptic.wav", "risset_decelerating_haptic.wav"),
  shepard = c("shepard_falling_haptic.wav", "shepard_rising_haptic.wav")
)

# ============================================================
# ANCHOR / CONSTANT STIMULI
# These are the "no change" neutral stimuli (e.g. pitch_constant,
# ramp_90to90BPM). They are expected to have zero or near-zero
# variance across modalities since there's no illusion to perceive.
# Excluded from per-stimulus simple-effects ANOVAs (Section 8)
# because a repeated-measures ANOVA on a constant vector has a
# singular covariance matrix and cannot compute sphericity —
# this is not a data error, it's the expected behavior for a
# neutral anchor.
# ============================================================

ANCHOR_STIMULI <- c(
  "pitch_constant_220to220Hz.wav",
  "ramp_90to90BPM_12s_210Hz.wav"
)

# ============================================================
# 1. LOAD DATA
# ============================================================

risset_ranking    <- read.table(paste0(root_path, "risset_ranking.txt"),    header = TRUE, sep = "\t")
risset_flashcards <- read.table(paste0(root_path, "risset_flashcards.txt"), header = TRUE, sep = "\t")
shepard_ranking    <- read.table(paste0(root_path, "shepard_ranking.txt"),    header = TRUE, sep = "\t")
shepard_flashcards <- read.table(paste0(root_path, "shepard_flashcards.txt"), header = TRUE, sep = "\t")

# ============================================================
# 2. PREPARE FACTORS
# ============================================================

prepare_df <- function(df) {
  df %>% mutate(
    Participant = factor(Participant),
    Modality    = factor(Modality, levels = c("audio", "haptic", "both")),
    Filename    = factor(Filename)
  )
}

risset_ranking    <- prepare_df(risset_ranking)
risset_flashcards <- prepare_df(risset_flashcards)
shepard_ranking    <- prepare_df(shepard_ranking)
shepard_flashcards <- prepare_df(shepard_flashcards)

datasets <- list(
  risset_ranking    = risset_ranking,
  risset_flashcards = risset_flashcards,
  shepard_ranking    = shepard_ranking,
  shepard_flashcards = shepard_flashcards
)

stimulus_family <- list(
  risset_ranking    = "risset",
  risset_flashcards = "risset",
  shepard_ranking    = "shepard",
  shepard_flashcards = "shepard"
)

# ============================================================
# 3. DATA OVERVIEW
# ============================================================

cat("=== DATA OVERVIEW ===\n\n")
for (nm in names(datasets)) {
  df <- datasets[[nm]]
  cat(sprintf("[ %s ]\n", nm))
  cat(sprintf("  Participants : %d\n",   n_distinct(df$Participant)))
  cat(sprintf("  Modalities   : %s\n",   paste(levels(df$Modality), collapse = ", ")))
  cat(sprintf("  Stimuli      : %d unique filenames\n", n_distinct(df$Filename)))
  cat(sprintf("  Total rows   : %d\n\n", nrow(df)))
}

# ============================================================
# 4. SUMMARY STATISTICS
# ============================================================

cat("\n=== SUMMARY STATISTICS ===\n")

summarise_dataset <- function(df, label) {
  cat(sprintf("\n--- %s ---\n", label))
  
  cat("\nBy Modality:\n")
  print(df %>% group_by(Modality) %>% get_summary_stats(Score_N, type = "mean_sd"))
  
  cat("\nBy Stimulus:\n")
  print(df %>% group_by(Filename) %>% get_summary_stats(Score_N, type = "mean_sd"))
  
  cat("\nBy Modality x Stimulus:\n")
  print(df %>% group_by(Modality, Filename) %>% get_summary_stats(Score_N, type = "mean_sd"))
}

for (nm in names(datasets)) summarise_dataset(datasets[[nm]], nm)

# ============================================================
# 5. ASSUMPTION CHECKS
# ============================================================

cat("\n\n=== ASSUMPTION CHECKS ===\n")

check_assumptions <- function(df, label) {
  cat(sprintf("\n--- %s ---\n", label))
  
  # Outliers
  cat("\nOutliers (by Modality x Filename):\n")
  out <- df %>% group_by(Modality, Filename) %>% identify_outliers(Score_N)
  if (nrow(out) > 0) {
    print(out)
    cat(sprintf("  -> %d outlier(s) found\n", nrow(out)))
  } else {
    cat("  -> No outliers detected\n")
  }
  
  # Normality — skip constant groups (Shapiro-Wilk undefined)
  cat("\nShapiro-Wilk normality (by Modality x Filename):\n")
  constant <- df %>%
    group_by(Modality, Filename) %>%
    filter(n_distinct(Score_N) == 1)
  if (nrow(constant) > 0) {
    cat("  NOTE: Following groups have identical values — Shapiro-Wilk skipped:\n")
    print(constant %>% distinct(Modality, Filename))
  }
  norm <- df %>%
    group_by(Modality, Filename) %>%
    filter(n_distinct(Score_N) > 1) %>%
    shapiro_test(Score_N)
  print(norm)
  viol <- norm %>% filter(p < 0.05)
  if (nrow(viol) > 0) {
    cat(sprintf("  WARNING: Normality violated in %d group(s)\n", nrow(viol)))
  } else {
    cat("  -> All tested groups meet normality assumption\n")
  }
  cat("  NOTE: Low power of normality tests expected with small n.\n")
}

for (nm in names(datasets)) check_assumptions(datasets[[nm]], nm)

# ============================================================
# 6. TWO-WAY REPEATED MEASURES ANOVA
# ============================================================

cat("\n\n=== TWO-WAY REPEATED MEASURES ANOVA ===\n")
cat("Factors: Modality (3) x Stimulus (7), both within-subject\n")
cat("Sphericity correction: Greenhouse-Geisser applied where Mauchly p < .05\n\n")

run_anova <- function(df, label) {
  cat(sprintf("\n--- %s ---\n", label))
  
  result <- anova_test(
    data        = df,
    dv          = Score_N,
    wid         = Participant,
    within      = c(Modality, Filename),
    effect.size = "pes",
    type        = 3
  )
  
  tbl <- get_anova_table(result, correction = "GG") %>% data.frame()
  cat("\nANOVA Table (Greenhouse-Geisser corrected where needed):\n")
  print(tbl)
  
  # Extract key p-values and effect sizes
  get_row <- function(effect) tbl %>% filter(Effect == effect)
  
  mod_row  <- get_row("Modality")
  stim_row <- get_row("Filename")
  int_row  <- get_row("Modality:Filename")
  
  cat("\nInterpretation:\n")
  cat(strrep("-", 55), "\n")
  
  report_effect <- function(row, name) {
    if (nrow(row) == 0) return(invisible(NULL))
    sig <- ifelse(row$p < .05, "SIGNIFICANT", "not significant")
    cat(sprintf("  %-14s p = %.4f, pes = %.3f  [%s]\n",
                paste0(name, ":"), row$p, row$pes, sig))
  }
  
  report_effect(mod_row,  "MODALITY")
  report_effect(stim_row, "STIMULUS")
  report_effect(int_row,  "INTERACTION")
  cat(strrep("-", 55), "\n")
  
  # G*Power: extract Cohen's f for Modality main effect
  if (nrow(mod_row) > 0 && !is.na(mod_row$pes)) {
    pes <- mod_row$pes
    f   <- sqrt(pes / (1 - pes))
    cat(sprintf("\n  G*Power input (Modality main effect):\n"))
    cat(sprintf("    partial eta^2 = %.4f\n", pes))
    cat(sprintf("    Cohen's f     = %.4f\n", f))
    cat( "    -> Enter f into G*Power: F tests > ANOVA: Repeated measures,\n")
    cat( "       within factors, alpha=0.05, power=0.80, groups=1, measurements=3\n")
  }
  
  list(table = tbl,
       mod_p  = if (nrow(mod_row)  > 0) mod_row$p  else NA,
       stim_p = if (nrow(stim_row) > 0) stim_row$p else NA,
       int_p  = if (nrow(int_row)  > 0) int_row$p  else NA,
       mod_pes = if (nrow(mod_row) > 0) mod_row$pes else NA)
}

anova_results <- lapply(names(datasets), function(nm) {
  run_anova(datasets[[nm]], nm)
})
names(anova_results) <- names(datasets)

# ============================================================
# 7. POST-HOC TESTS (Bonferroni)
# Only run when omnibus main effect is significant
# ============================================================

cat("\n\n=== POST-HOC COMPARISONS (Bonferroni) ===\n")

run_posthoc <- function(df, anova_res, label) {
  cat(sprintf("\n--- %s ---\n", label))
  out <- list()
  
  # Modality
  if (!is.na(anova_res$mod_p) && anova_res$mod_p < .05) {
    cat("\nModality pairwise comparisons:\n")
    ph <- df %>%
      pairwise_t_test(Score_N ~ Modality, paired = TRUE,
                      p.adjust.method = "bonferroni")
    print(ph)
    out$modality <- ph
  } else {
    cat("\nModality: omnibus p >= .05 — post-hoc skipped\n")
  }
  
  # Stimulus
  if (!is.na(anova_res$stim_p) && anova_res$stim_p < .05) {
    cat("\nStimulus pairwise comparisons:\n")
    ph <- df %>%
      pairwise_t_test(Score_N ~ Filename, paired = TRUE,
                      p.adjust.method = "bonferroni")
    print(ph)
    out$stimulus <- ph
  } else {
    cat("\nStimulus: omnibus p >= .05 — post-hoc skipped\n")
  }
  
  out
}

posthoc_results <- lapply(names(datasets), function(nm) {
  run_posthoc(datasets[[nm]], anova_results[[nm]], nm)
})
names(posthoc_results) <- names(datasets)

# ============================================================
# 8. SIMPLE EFFECTS (only if interaction significant)
# ============================================================
# NOTE ON ANCHOR STIMULI:
# Neutral/anchor stimuli (e.g. pitch_constant, ramp_90to90BPM) are
# expected to show zero variance across modalities, since there is
# no pitch/tempo change for a participant to perceive a direction on.
# A repeated-measures ANOVA on a constant vector has a singular
# covariance matrix, so sphericity cannot be computed and
# rstatix::anova_test() returns a malformed result for that group,
# which breaks the internal unnest() when combined with the other
# (valid) groups. We therefore explicitly exclude ANCHOR_STIMULI
# before running the per-stimulus "Modality effect" test, and wrap
# each per-group call in tryCatch as a second safety net in case any
# other stimulus/modality group is degenerate for a given dataset.
# ============================================================

cat("\n\n=== SIMPLE MAIN EFFECTS ===\n")

run_simple_effects <- function(df, anova_res, label) {
  if (is.na(anova_res$int_p) || anova_res$int_p >= .05) {
    cat(sprintf("\n  [ %s ] Interaction p >= .05 — simple effects skipped\n", label))
    return(invisible(NULL))
  }
  
  cat(sprintf("\n--- %s (interaction significant) ---\n", label))
  
  # Drop anchor/neutral stimuli — zero variance across modalities by
  # design, not a meaningful "does modality differ" test, and breaks
  # sphericity computation if left in.
  present_anchors <- intersect(ANCHOR_STIMULI, levels(df$Filename))
  if (length(present_anchors) > 0) {
    cat(sprintf("\n  Excluding anchor stimulus/stimuli from simple effects: %s\n",
                paste(present_anchors, collapse = ", ")))
  }
  df_eff <- df %>% filter(!Filename %in% ANCHOR_STIMULI) %>% droplevels()
  
  # Effect of Modality at each Stimulus
  # Run per-Filename manually with tryCatch so one degenerate group
  # (e.g. unbalanced data, zero variance) doesn't abort the whole loop.
  cat("\nModality effect at each Stimulus level:\n")
  mod_simple <- map_dfr(levels(df_eff$Filename), function(f) {
    sub <- df_eff %>% filter(Filename == f)
    res <- tryCatch({
      tbl <- anova_test(data = sub, dv = Score_N, wid = Participant,
                        within = Modality, effect.size = "pes") %>%
        get_anova_table()
      class(tbl) <- "data.frame"  # force-strip anova_test/rstatix_test subclasses so map_dfr can rbind it
      tbl
    }, error = function(e) {
      cat(sprintf("  WARNING: skipped Filename = '%s' (%s)\n", f, conditionMessage(e)))
      NULL
    })
    if (!is.null(res)) res$Filename <- f
    res
  })
  if (nrow(mod_simple) > 0) {
    mod_simple <- mod_simple %>% adjust_pvalue(method = "bonferroni")
  }
  print(mod_simple)
  
  # Effect of Stimulus at each Modality
  # (Anchor stimuli intentionally excluded here too, for consistency —
  # remove the df_eff -> df swap below if you want the anchor included
  # in this direction of the test.)
  cat("\nStimulus effect at each Modality level:\n")
  stim_simple <- map_dfr(levels(df_eff$Modality), function(m) {
    sub <- df_eff %>% filter(Modality == m)
    res <- tryCatch({
      tbl <- anova_test(data = sub, dv = Score_N, wid = Participant,
                        within = Filename, effect.size = "pes") %>%
        get_anova_table()
      class(tbl) <- "data.frame"  # force-strip anova_test/rstatix_test subclasses so map_dfr can rbind it
      tbl
    }, error = function(e) {
      cat(sprintf("  WARNING: skipped Modality = '%s' (%s)\n", m, conditionMessage(e)))
      NULL
    })
    if (!is.null(res)) res$Modality <- m
    res
  })
  if (nrow(stim_simple) > 0) {
    stim_simple <- stim_simple %>% adjust_pvalue(method = "bonferroni")
  }
  print(stim_simple)
  
  list(modality_simple = mod_simple, stimulus_simple = stim_simple)
}

simple_results <- lapply(names(datasets), function(nm) {
  run_simple_effects(datasets[[nm]], anova_results[[nm]], nm)
})
names(simple_results) <- names(datasets)

# ============================================================
# 9. PLANNED CONTRAST: Haptic vs Audio — illusion stimuli only
# Core transfer question: do haptic scores go in the same
# direction as audio scores for illusion stimuli?
# ============================================================

cat("\n\n=== PLANNED CONTRAST: Haptic vs Audio — Illusion Stimuli ===\n")
cat("(Bonferroni corrected across 4 contrasts: 2 tasks x 2 stimulus sets)\n\n")

run_transfer_contrast <- function(df, family, label) {
  cat(sprintf("\n--- %s ---\n", label))
  
  illusion_files <- ILLUSION_STIMULI[[family]]
  df_ill <- df %>% filter(Filename %in% illusion_files,
                          Modality %in% c("audio", "haptic"))
  
  if (n_distinct(df_ill$Participant) < 2) {
    cat("  Not enough participants for contrast — skipped\n")
    return(invisible(NULL))
  }
  
  cat(sprintf("  Illusion stimuli: %s\n", paste(illusion_files, collapse = ", ")))
  cat(sprintf("  Rows in subset: %d\n\n", nrow(df_ill)))
  
  # Paired t-test: haptic vs audio, collapsed across illusion stimuli
  audio_scores  <- df_ill %>% filter(Modality == "audio")  %>%
    group_by(Participant) %>% summarise(m = mean(Score_N), .groups = "drop")
  haptic_scores <- df_ill %>% filter(Modality == "haptic") %>%
    group_by(Participant) %>% summarise(m = mean(Score_N), .groups = "drop")
  
  combined <- inner_join(audio_scores, haptic_scores,
                         by = "Participant", suffix = c("_audio", "_haptic"))
  
  cat("  Per-participant means (illusion stimuli only):\n")
  print(combined)
  
  t_res <- t.test(combined$m_haptic, combined$m_audio,
                  paired = TRUE, alternative = "two.sided")
  
  # Bonferroni correction across 4 planned contrasts
  p_adj <- min(t_res$p.value * 4, 1)
  
  cat(sprintf("\n  Paired t-test: t(%d) = %.3f, p = %.4f, p.adj (Bonf x4) = %.4f\n",
              t_res$parameter, t_res$statistic, t_res$p.value, p_adj))
  cat(sprintf("  Mean audio score  (illusion): %.3f\n", mean(combined$m_audio)))
  cat(sprintf("  Mean haptic score (illusion): %.3f\n", mean(combined$m_haptic)))
  
  same_direction <- sign(mean(combined$m_audio)) == sign(mean(combined$m_haptic))
  cat(sprintf("  Same direction (transfer indicator): %s\n",
              ifelse(same_direction, "YES", "NO")))
  
  list(t_result = t_res, p_adj = p_adj, data = combined)
}

contrast_results <- lapply(names(datasets), function(nm) {
  run_transfer_contrast(datasets[[nm]], stimulus_family[[nm]], nm)
})
names(contrast_results) <- names(datasets)

# ============================================================
# 10. EXPORT
# ============================================================

cat("\n\n=== EXPORTING RESULTS ===\n")

safe_write <- function(x, path) {
  if (!is.null(x) && nrow(x) > 0) {
    write.csv(x, path, row.names = FALSE)
    cat(sprintf("  Saved: %s\n", basename(path)))
  }
}

for (nm in names(datasets)) {
  # ANOVA table
  safe_write(anova_results[[nm]]$table,
             paste0(results_dir, "anova_", nm, ".csv"))
  
  # Post-hoc modality
  safe_write(posthoc_results[[nm]]$modality,
             paste0(results_dir, "posthoc_", nm, "_modality.csv"))
  
  # Post-hoc stimulus
  safe_write(posthoc_results[[nm]]$stimulus,
             paste0(results_dir, "posthoc_", nm, "_stimulus.csv"))
  
  # Simple effects (only present when interaction was significant)
  safe_write(simple_results[[nm]]$modality_simple,
             paste0(results_dir, "simple_effects_", nm, "_modality.csv"))
  safe_write(simple_results[[nm]]$stimulus_simple,
             paste0(results_dir, "simple_effects_", nm, "_stimulus.csv"))
  
  # Long format data for plotting
  write.csv(datasets[[nm]],
            paste0(results_dir, nm, "_long.csv"), row.names = FALSE)
  cat(sprintf("  Saved: %s_long.csv\n", nm))
}

cat("\nAnalysis complete.\n")
cat("Run plotting.R next for visualizations.\n")
cat(sprintf("Results saved to: %s\n", results_dir))