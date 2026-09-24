#let data = json("mrs.json")
#set page(paper: "a4", margin: 16mm)
#set text(size: 11pt)

#align(center)[
  #text(size: 22pt, weight: "bold", fill: rgb("#1f4e79"))[Recoverage]
  #v(1mm)
  #text(size: 12pt, fill: rgb("#475569"))[Merge Readiness Score]
  #v(2mm)
  #text(size: 40pt, weight: "bold")[#data.score]
  #text(size: 14pt)[ out of 100]
  #v(3mm)
  #box(fill: rgb(data.badge_color), inset: (x: 12pt, y: 7pt), radius: 4pt)[
    #text(fill: white, weight: "bold", size: 13pt)[#data.badge]
  ]
  #v(2mm)
  #text(size: 11pt)[Gate: #data.gate]
  #v(2mm)
  #text(size: 10pt)[#data.blurb]
]

#v(6mm)
#text(size: 16pt, weight: "bold", fill: rgb("#1f4e79"))[Score factors]
#v(2mm)
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

#v(5mm)
#text(size: 16pt, weight: "bold", fill: rgb("#1f4e79"))[Coverage by module]
#v(2mm)
#text(size: 9pt, fill: rgb("#64748b"))[Vector bars drawn by Typst from the coverage JSON. Not a placeholder.]
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

#v(4mm)
#text(size: 16pt, weight: "bold", fill: rgb("#1f4e79"))[Gap severity]
#v(2mm)
#for item in data.severities {
  let width = if item.count == 0 { 0% } else { calc.min(70%, item.count * 8%) }
  block[
    #box(width: 18%)[#item.name]
    #box(width: width, height: 9pt, fill: rgb(item.color))
    #h(6pt)
    #item.count
  ]
}

#v(4mm)
#text(size: 16pt, weight: "bold", fill: rgb("#1f4e79"))[Property-based testing]
#v(2mm)
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

#v(4mm)
#text(size: 16pt, weight: "bold", fill: rgb("#1f4e79"))[Mutation, prompt coverage, blast radius, timing]
#v(2mm)
#text[#data.mutation]
#v(1mm)
#text[#data.prompt]
#v(1mm)
#text[#data.blast]
#v(1mm)
#text[#data.timing]

#v(4mm)
#text(size: 16pt, weight: "bold", fill: rgb("#1f4e79"))[Authenticity scorecard]
#v(2mm)
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

#v(4mm)
#text(size: 16pt, weight: "bold", fill: rgb("#1f4e79"))[Autonomous suggestions]
#v(2mm)
#for item in data.suggestions {
  [- #item]
}

#v(4mm)
#text(size: 12pt, weight: "bold")[Rubric]
#v(2mm)
#text(size: 9pt)[#data.rubric]
