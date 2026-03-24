# CLAUDE.md — AI Assistant Guide for Google Chrome Samples

## Project Overview

A collection of 100+ self-contained samples demonstrating new Google Chrome features. Each sample corresponds to a feature entry on https://www.chromestatus.com/features. The site is hosted via GitHub Pages at https://googlechrome.github.io/samples/.

**License**: Apache 2.0

## Repository Structure

```
samples/
├── _config.yml              # Jekyll site configuration
├── _layouts/default.html    # Master page template
├── _includes/               # Reusable Jekyll template components
│   ├── output_helper.html   # ChromeSamples.log() utility
│   ├── js_snippet.html      # JS code display include
│   └── css_snippet.html     # CSS code display include
├── styles/main.css          # Global stylesheet
├── images/                  # Shared images (favicon, icons)
├── media/                   # Shared media assets
├── SAMPLE_STARTING_POINT/   # Template for creating new samples
├── package.json             # NPM config (ESLint dependencies)
├── Gemfile                  # Ruby/Jekyll dependencies
├── .eslintrc                # ESLint configuration
├── .travis.yml              # CI configuration
└── <feature-name>/          # ~102 individual sample directories
    ├── index.html           # Main page (Jekyll front matter)
    ├── demo.js              # Feature demonstration code
    ├── README.md            # Feature documentation
    └── style.css            # (optional) Sample-specific styles
```

## Build & Development

### Prerequisites
- Node.js + npm (for linting)
- Ruby + Bundler (for Jekyll)

### Commands

| Command | Purpose |
|---------|---------|
| `npm install` | Install linting dependencies |
| `npm run lint` | Run ESLint across all samples |
| `bundle install` | Install Jekyll dependencies |
| `bundle exec jekyll build` | Build the static site |
| `bundle exec jekyll serve` | Local dev server |

### CI Pipeline (Travis CI)
Runs on all branches:
1. `npm install`
2. `npm run lint` — must pass with zero errors
3. `bundle exec jekyll build` — must complete successfully

## Code Style & Linting

- **Style guide**: [Google JavaScript Style Guide](http://google.github.io/styleguide/javascriptguide.xml)
- **Linter**: ESLint v1.x with `eslint-config-google`
- **Custom overrides** (`.eslintrc`):
  - `arrow-parens`: `"as-needed"` (no parens for single params)
  - `require-jsdoc`: disabled
  - `no-inline-comments`: disabled
- **Ignored paths** (`.eslintignore`): `_site/`, `vendor/`, `service-worker/serviceworker-cache-polyfill.js`, `decorators-es7/`
- **Global**: `ChromeSamples` is a recognized global variable

Always run `npm run lint` before committing to catch style violations.

## Key Conventions

### Creating a New Sample
1. Copy `SAMPLE_STARTING_POINT/` to a new directory named after the feature
2. Update Jekyll front matter in `index.html`:
   ```yaml
   ---
   feature_name: "Feature Name"
   chrome_version: XX
   feature_id: XXXXX
   local_css_files: ['style.css']
   local_js_files: ['demo.js']
   ---
   ```
3. Write the demo in `demo.js`
4. Add a `README.md` describing the feature
5. Use Jekyll includes (`output_helper.html`, `js_snippet.html`, `css_snippet.html`) for consistent presentation

### ChromeSamples Helper API
Available when `output_helper.html` is included:
- `ChromeSamples.log()` — Log output to the page
- `ChromeSamples.clearLog()` — Clear log output
- `ChromeSamples.setStatus()` — Set a status message
- `ChromeSamples.setContent()` — Replace content dynamically

### Git Workflow
- **Production branch**: `gh-pages` (serves GitHub Pages)
- **PRs**: File against `gh-pages` branch
- Each sample is self-contained — changes to one sample should not affect others

## Important Notes for AI Assistants

- **No test suite**: This repo has demonstrative samples, not unit tests. Validation is via `npm run lint` and `bundle exec jekyll build`.
- **Self-contained samples**: Each feature directory is independent. Avoid cross-sample dependencies.
- **Jekyll templating**: Files with YAML front matter (`---`) are processed by Jekyll. Files without front matter are served as-is.
- **Browser-only code**: All JavaScript targets the browser environment. No Node.js runtime code in samples.
- **Shared infrastructure is minimal**: Only `_layouts/`, `_includes/`, `styles/`, and `images/` are shared. Do not add new shared utilities without strong justification.
- **Keep samples simple**: Each sample should demonstrate one Chrome feature clearly. Minimal code, no frameworks.
