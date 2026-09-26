#let data = json("mrs.json")
#set page(paper: "a4", margin: 16mm)
#set text(size: 11pt)
#set heading(numbering: none)

#align(center)[
  #text(size: 22pt, weight: "bold", fill: rgb("#1f4e79"))[Recoverage]
  #v(1mm)
  #text(size: 12pt, fill: rgb("#475569"))[#data.project]
  #v(2mm)
  #circle(radius: 34pt, stroke: 7pt + rgb(data.badge_color))[
    #align(center + horizon)[#text(size: 16pt, weight: "bold")[#data.score]]
  ]
  #v(2mm)
  #text(size: 12pt)[#data.score out of 100]
  #v(2mm)
  #box(fill: rgb(data.badge_color), inset: (x: 12pt, y: 7pt), radius: 4pt)[
    #text(fill: white, weight: "bold", size: 12pt)[#data.badge]
  ]
  #v(2mm)
  #text(size: 10pt)[Gate: #data.gate]
  #v(2mm)
  #text(size: 10pt)[#data.blurb]
]

#v(4mm)
#grid(
  columns: (1fr, 1fr, 1fr, 1fr),
  gutter: 8pt,
  box(fill: rgb("#f4f7fb"), inset: 8pt, width: 100%)[#text(size: 9pt)[Statements\ #data.line]],
  box(fill: rgb("#f4f7fb"), inset: 8pt, width: 100%)[#text(size: 9pt)[Branches\ #data.branch]],
  box(fill: rgb("#f4f7fb"), inset: 8pt, width: 100%)[#text(size: 9pt)[Gaps\ #data.gap_count]],
  box(fill: rgb("#f4f7fb"), inset: 8pt, width: 100%)[#text(size: 9pt)[Mutation\ #data.mutation_ran]],
)

#v(4mm)
#outline()

= Score factors
#table(
  columns: (1.6fr, 0.6fr, 0.5fr, 2.4fr),
  inset: 6pt,
  fill: (x, y) => if y == 0 { rgb("#1f4e79") } else { rgb("#f4f7fb") },
  [#text(fill: white, weight: "bold")[Factor]],
  [#text(fill: white, weight: "bold")[Earned]],
  [#text(fill: white, weight: "bold")[Max]],
  [#text(fill: white, weight: "bold")[Detail]],
  ..data.factors.map(factor => (
    [#factor.title],
    [#factor.earned],
    [#factor.maximum],
    [#factor.detail],
  )).flatten(),
)

= Coverage by module
#text(size: 9pt, fill: rgb("#64748b"))[Bars are drawn from the analysis. A gray bar is not a measured zero.]
#v(2mm)
#for item in data.modules {
  let pct = if item.line_percent == none { 0 } else { item.line_percent }
  block(width: 100%, above: 3pt)[
    #box(width: 28%)[#text(size: 9pt)[#item.name]]
    #box(width: pct * 0.55%, height: 9pt, fill: rgb("#1f7a6b"))
    #h(6pt)
    #text(size: 9pt)[#if item.line_percent == none [not measured] else [#item.line_percent%]]
  ]
}

= Gap severity
#for item in data.severities {
  let width = if item.count == 0 { 0% } else { calc.min(70%, item.count * 8%) }
  block[
    #box(width: 18%)[#item.name]
    #box(width: width, height: 9pt, fill: rgb(item.color))
    #h(6pt)
    #item.count
  ]
}

= Files
#if data.files.len() == 0 [
  No files.
] else [
  #table(
    columns: (2.2fr, 0.7fr, 0.8fr, 0.6fr),
    inset: 5pt,
    [File], [Statements], [Coverage], [Gaps],
    ..data.files.map(row => (
      [#row.path],
      [#row.statements],
      [#row.coverage],
      [#row.gaps],
    )).flatten(),
  )
  #if data.files_omitted > 0 [
    #text(size: 9pt)[+#data.files_omitted more files are in report.html.]
  ]
]

= Findings
#if data.findings.len() == 0 [
  No gaps recorded.
] else [
  #for item in data.findings [
    #block(above: 6pt)[
      #text(weight: "bold")[#item.id · #item.severity · #item.title]
      #linebreak()
      #text(size: 9pt)[#item.where]
      #linebreak()
      #item.why
    ]
  ]
]

= Property-based testing
#text[#data.pbt.note]
#v(2mm)
#if data.pbt.rows.len() == 0 [
  No property trials.
] else [
  #table(
    columns: (1.4fr, 0.7fr, 0.7fr, 0.7fr),
    inset: 5pt,
    [Symbol], [Trials], [Passed], [Failed],
    ..data.pbt.rows.map(row => ([#row.symbol], [#row.trials], [#row.passed], [#row.failed])).flatten(),
  )
]

= Mutation, prompt coverage, blast radius, timing
#text[#data.mutation]
#v(1mm)
#text[#data.prompt]
#v(1mm)
#text[#data.blast]
#v(1mm)
#text[#data.timing]

= Authenticity scorecard
#text(size: 9pt)[#data.audit.note]
#v(2mm)
#if data.audit.rows.len() == 0 [
  No authenticity rows.
] else [
  #table(
    columns: (2.2fr, 0.8fr, 0.9fr, 0.7fr),
    inset: 5pt,
    [Dimension], [Value], [Threshold], [Status],
    ..data.audit.rows.map(row => ([#row.dimension], [#row.value], [#row.threshold], [#row.status])).flatten(),
  )
]

= Suggestions
#for item in data.suggestions [
  [- #item]
]

= Rubric
#text(size: 9pt)[#data.rubric]
