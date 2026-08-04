# ============================================================
# plotting.R
# Visualizations — Auditory Illusions Experiment
# ============================================================
# Run analysis.R first, or uncomment the CSV load block below.
#
# Three plot types per dataset (4 datasets = 12 plots total):
#   Plot A: Boxplot — Score_N by Modality (x-axis)
#   Plot B: Boxplot — Score_N by Stimulus (x-axis)
#   Plot C: Individual points + mean +/- SE by Stimulus x Modality
# ============================================================

library(tidyverse)
library(rstatix)
library(ggpubr)

# ============================================================
# PATHS — edit here
# ============================================================

root_path   <- "C:/Users/luern/Documents/CodingProjects/AuditoryIllusions/analysis/output/"
results_dir <- paste0(root_path, "anova_results/")
plots_dir   <- paste0(root_path, "plots/")
if (!dir.exists(plots_dir)) dir.create(plots_dir, recursive = TRUE)

# ============================================================
# LOAD DATA
# Option 1: already in environment from analysis.R — skip block
# Option 2: load from saved CSVs (uncomment below)
# ============================================================

# risset_ranking    <- read.csv(paste0(results_dir, "risset_ranking_long.csv"))
# risset_flashcards <- read.csv(paste0(results_dir, "risset_flashcards_long.csv"))
# shepard_ranking    <- read.csv(paste0(results_dir, "shepard_ranking_long.csv"))
# shepard_flashcards <- read.csv(paste0(results_dir, "shepard_flashcards_long.csv"))

# ============================================================
# STIMULUS ORDER & LABELS
# Controls ordered descending -> neutral -> ascending,
# then illusion stimuli last
# ============================================================

risset_order <- c(
  "ramp_90to60BPM_12s_210Hz.wav",
  "ramp_90to70BPM_12s_210Hz.wav",
  "ramp_90to90BPM_12s_210Hz.wav",
  "ramp_90to110BPM_12s_210Hz.wav",
  "ramp_90to120BPM_12s_210Hz.wav",
  "risset_decelerating_haptic.wav",
  "risset_accelerating_haptic.wav"
)

shepard_order <- c(
  "pitch_decrease_strong_220to110Hz.wav",
  "pitch_decrease_mild_220to156Hz.wav",
  "pitch_constant_220to220Hz.wav",
  "pitch_increase_mild_220to311Hz.wav",
  "pitch_increase_strong_220to440Hz.wav",
  "shepard_falling_haptic.wav",
  "shepard_rising_haptic.wav"
)

risset_labels <- c(
  "ramp_90to60BPM_12s_210Hz.wav"    = "60 BPM",
  "ramp_90to70BPM_12s_210Hz.wav"    = "70 BPM",
  "ramp_90to90BPM_12s_210Hz.wav"    = "90 BPM\n(neutral)",
  "ramp_90to110BPM_12s_210Hz.wav"   = "110 BPM",
  "ramp_90to120BPM_12s_210Hz.wav"   = "120 BPM",
  "risset_decelerating_haptic.wav"  = "Risset\nDecel.",
  "risset_accelerating_haptic.wav"  = "Risset\nAccel."
)

shepard_labels <- c(
  "pitch_decrease_strong_220to110Hz.wav" = "Dec\nStrong",
  "pitch_decrease_mild_220to156Hz.wav"   = "Dec\nMild",
  "pitch_constant_220to220Hz.wav"        = "Constant\n(neutral)",
  "pitch_increase_mild_220to311Hz.wav"   = "Inc\nMild",
  "pitch_increase_strong_220to440Hz.wav" = "Inc\nStrong",
  "shepard_falling_haptic.wav"           = "Shepard\nFalling",
  "shepard_rising_haptic.wav"            = "Shepard\nRising"
)

modality_labels <- c(
  "audio"  = "Audio only",
  "haptic" = "Haptic only",
  "both"   = "Audio + Haptic"
)

# ============================================================
# REFACTOR FACTORS
# ============================================================

refactor <- function(df, stimulus_type) {
  order  <- if (stimulus_type == "risset") risset_order  else shepard_order
  
  missing <- setdiff(order, unique(df$Filename))
  if (length(missing) > 0) {
    warning(sprintf("[%s] Stimuli in order not found in data: %s",
                    stimulus_type, paste(missing, collapse = ", ")))
  }
  
  df %>% mutate(
    Participant = factor(Participant),
    Modality    = factor(Modality,  levels = c("audio", "haptic", "both")),
    Filename    = factor(Filename,  levels = order)
  )
}

risset_ranking    <- refactor(risset_ranking,    "risset")
risset_flashcards <- refactor(risset_flashcards, "risset")
shepard_ranking    <- refactor(shepard_ranking,    "shepard")
shepard_flashcards <- refactor(shepard_flashcards, "shepard")

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
# SHARED THEME & COLORS
# ============================================================

theme_illusions <- theme_minimal(base_size = 14) +
  theme(
    axis.text.x        = element_text(size = 11, angle = 35, hjust = 1),
    axis.title.x       = element_text(size = 13, face = "bold"),
    axis.text.y        = element_text(size = 11),
    axis.title.y       = element_text(size = 13, face = "bold"),
    legend.title       = element_text(size = 11, face = "bold"),
    legend.text        = element_text(size = 10),
    plot.subtitle      = element_text(size = 12, color = "gray40"),
    plot.title         = element_blank(),
    panel.grid.major.y = element_line(color = "gray85", linewidth = 0.5),
    panel.grid.minor.y = element_line(color = "gray92", linewidth = 0.3),
    panel.grid.major.x = element_blank(),
    panel.grid.minor   = element_blank()
  )

modality_colors <- c(
  "audio"  = "#FC4E07",
  "haptic" = "#E7B800",
  "both"   = "#00AFBB"
)

# ============================================================
# HELPER: significance stars from post-hoc pairwise t-test
# ============================================================
# NOTE: A paired t-test needs at least 2 non-missing differences per
# pair being compared. If a participant is missing a rating for one
# member of a Modality/Filename pair (e.g. incomplete trial data),
# that pair can drop below 2 valid observations and t.test() errors
# with "not enough 'x' observations". Wrapped in tryCatch so one bad
# comparison just skips its stars instead of aborting the whole
# plotting loop — check the console warning to see which dataset and
# variable was affected, then verify that raw data for completeness.
# ============================================================

get_stars <- function(df, x_var) {
  formula <- as.formula(paste("Score_N ~", x_var))
  ph <- tryCatch({
    df %>%
      pairwise_t_test(formula, paired = TRUE, p.adjust.method = "bonferroni") %>%
      add_significance("p.adj") %>%
      filter(!p.adj.signif %in% c("ns"))
  }, error = function(e) {
    cat(sprintf("  WARNING: get_stars('%s') skipped — %s\n", x_var, conditionMessage(e)))
    tibble()
  })
  
  if (nrow(ph) > 0) {
    base_y <- max(df$Score_N, na.rm = TRUE)
    ph <- ph %>%
      mutate(y.position = base_y + 0.15 + (row_number() - 1) * 0.2)
  }
  ph
}

# ============================================================
# PLOT A: Boxplot — Score_N by Modality
# ============================================================

plot_A_modality <- function(df, subtitle_text) {
  stars <- get_stars(df, "Modality")
  
  p <- ggplot(df, aes(x = Modality, y = Score_N, fill = Modality)) +
    geom_boxplot(color = "black", outlier.shape = NA, width = 0.5, alpha = 0.85) +
    geom_jitter(width = 0.12, size = 1.8, alpha = 0.5, color = "gray30") +
    scale_fill_manual(values = modality_colors,
                      labels = modality_labels,
                      name = "Modality") +
    scale_x_discrete(labels = modality_labels) +
    geom_hline(yintercept = 0, linetype = "dashed",
               color = "gray50", linewidth = 0.5) +
    coord_cartesian(ylim = c(-1.25, 1.25)) +
    labs(x = "Modality", y = "Normalised Score",
         subtitle = subtitle_text) +
    theme_illusions +
    theme(legend.position = "none")
  
  if (nrow(stars) > 0) {
    p <- p + stat_pvalue_manual(stars, label = "p.adj.signif",
                                tip.length = 0.01, bracket.size = 0.5, size = 5)
  }
  p
}

# ============================================================
# PLOT B: Boxplot — Score_N by Stimulus
# ============================================================

plot_B_stimulus <- function(df, subtitle_text, xlabels) {
  stars <- get_stars(df, "Filename")
  
  p <- ggplot(df, aes(x = Filename, y = Score_N, fill = Filename)) +
    geom_boxplot(color = "black", outlier.shape = NA, width = 0.55, alpha = 0.85) +
    geom_jitter(width = 0.12, size = 1.8, alpha = 0.5, color = "gray30") +
    scale_fill_brewer(palette = "Set2") +
    scale_x_discrete(labels = xlabels) +
    geom_hline(yintercept = 0, linetype = "dashed",
               color = "gray50", linewidth = 0.5) +
    coord_cartesian(ylim = c(-1.25, 1.25)) +
    labs(x = "Stimulus", y = "Normalised Score",
         subtitle = subtitle_text) +
    theme_illusions +
    theme(legend.position = "none")
  
  if (nrow(stars) > 0) {
    p <- p + stat_pvalue_manual(stars, label = "p.adj.signif",
                                tip.length = 0.01, bracket.size = 0.5, size = 4)
  }
  p
}

# ============================================================
# PLOT C: Individual points + Mean +/- SE
# by Stimulus, coloured by Modality
# ============================================================

plot_C_individual <- function(df, subtitle_text, xlabels) {
  summary_df <- df %>%
    group_by(Filename, Modality) %>%
    summarise(
      mean_score = mean(Score_N,  na.rm = TRUE),
      se_score   = sd(Score_N,    na.rm = TRUE) / sqrt(n()),
      .groups    = "drop"
    )
  
  n_mod    <- nlevels(df$Modality)
  dodge_w  <- 0.6
  offsets  <- seq(-dodge_w/2, dodge_w/2, length.out = n_mod)
  names(offsets) <- levels(df$Modality)
  
  df_plot  <- df %>%
    mutate(x_jit = as.numeric(Filename) + offsets[as.character(Modality)]
           + runif(n(), -0.06, 0.06))
  sum_plot <- summary_df %>%
    mutate(x_pos = as.numeric(Filename) + offsets[as.character(Modality)])
  
  ggplot() +
    # Individual participant points
    geom_point(data = df_plot,
               aes(x = x_jit, y = Score_N, color = Modality, shape = Participant),
               size = 2, alpha = 0.45) +
    # This adds in the different shapes
    #scale_shape_manual(values = c(16, 17, 15), name = NULL) +
    
    # Mean diamonds
    geom_point(data = sum_plot,
               aes(x = x_pos, y = mean_score, color = Modality),
               size = 4, shape = 18) +
    # SE error bars
    geom_errorbar(data = sum_plot,
                  aes(x    = x_pos,
                      ymin = mean_score - se_score,
                      ymax = mean_score + se_score,
                      color = Modality),
                  width = 0.12, linewidth = 0.9) +
    scale_color_manual(values = modality_colors,
                       labels = modality_labels,
                       name   = NULL) +
    scale_x_continuous(
      breaks = seq_along(levels(df$Filename)),
      labels = xlabels[levels(df$Filename)]
    ) +
    geom_hline(yintercept = 0, linetype = "dashed",
               color = "gray50", linewidth = 0.5) +
    coord_cartesian(ylim = c(-1.25, 1.25)) +
    labs(x = "Stimulus", y = "Normalised Score",
         subtitle = subtitle_text) +
    theme_illusions +
    theme(
      legend.position      = c(0.01, 0.99),
      legend.justification = c(0, 1),
      legend.background    = element_rect(fill = "white", color = "gray80",
                                          linewidth = 0.4),
      legend.key           = element_blank(),
      legend.margin        = margin(4, 8, 4, 8)
    )
}

# ============================================================
# GENERATE ALL PLOTS
# ============================================================

subtitle_map <- list(
  risset_ranking    = "Risset — Ranking task",
  risset_flashcards = "Risset — Flashcard task",
  shepard_ranking    = "Shepard — Ranking task",
  shepard_flashcards = "Shepard — Flashcard task"
)

all_plots <- list()

for (nm in names(datasets)) {
  df      <- datasets[[nm]]
  family  <- stimulus_family[[nm]]
  sub     <- subtitle_map[[nm]]
  xlabels <- if (family == "risset") risset_labels else shepard_labels
  
  all_plots[[paste0("A_", nm)]] <- plot_A_modality(df, sub)
  all_plots[[paste0("B_", nm)]] <- plot_B_stimulus(df, sub, xlabels)
  all_plots[[paste0("C_", nm)]] <- plot_C_individual(df, sub, xlabels)
}

# Print all plots
for (nm in names(all_plots)) {
  cat(sprintf("Printing: %s\n", nm))
  print(all_plots[[nm]])
}

# ============================================================
# SAVE ALL PLOTS
# ============================================================

cat("\nSaving plots...\n")
for (nm in names(all_plots)) {
  out_path <- paste0(plots_dir, nm, ".png")
  ggsave(
    filename = out_path,
    plot     = all_plots[[nm]],
    width    = 10, height = 6, dpi = 300
  )
  cat(sprintf("  Saved: %s\n", basename(out_path)))
}

cat("\nPlotting complete.\n")
cat(sprintf("Plots saved to: %s\n", plots_dir))
cat("\nPlot guide:\n")
cat("  A_* = Boxplot by Modality (with jittered points + significance stars)\n")
cat("  B_* = Boxplot by Stimulus (with jittered points + significance stars)\n")
cat("  C_* = Individual points + mean +/- SE by Stimulus, coloured by Modality\n")