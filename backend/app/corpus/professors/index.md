# BIT Professor Corpus Index

- corpus_root: professors
- department_count: 22
- professor_count: 753
- source_page_count: 1485
- role: routing map only
- source_of_truth: individual professor Markdown files

## How To Use This Corpus

- Start here for broad, unclear, or cross-department professor questions.
- If the user names a department, open that department's `index.md`.
- If the user asks by research topic, identify likely departments from the routing table, then inspect those department indexes.
- Open individual professor files only after a department index suggests relevant candidates.
- Use department-qualified IDs such as `education/zhang-lishan` because names and slugs can repeat.
- If a question is interdisciplinary or the first department index is thin, search across the likely adjacent departments listed below.

## Department Routing Table

| Department | Slug | Count | Good For Queries About | Index |
|---|---:|---:|---|---|
| Aerospace Engineering | `aerospace-engineering` | 53 | aerospace systems, flight, spacecraft, aerodynamics, propulsion, structures, navigation, guidance, UAVs | [index.md](aerospace-engineering/index.md) |
| Automation | `automation` | 23 | control systems, robotics, intelligent control, autonomous systems, pattern recognition, system engineering | [index.md](automation/index.md) |
| Chemistry and Chemical Engineering | `chemistry-and-chemical-engineering` | 48 | chemistry, catalysis, polymers, electrochemistry, chemical engineering, nanomaterials, energetic materials | [index.md](chemistry-and-chemical-engineering/index.md) |
| Computer Science and Technology | `computer-science-and-technology` | 60 | AI, machine learning, NLP, computer vision, software engineering, networks, data mining, distributed systems | [index.md](computer-science-and-technology/index.md) |
| Cyberspace Science and Technology | `cyberspace-science-and-technology` | 11 | cybersecurity, cryptography, privacy, network security, data security, trustworthy computing | [index.md](cyberspace-science-and-technology/index.md) |
| Design and Arts | `design-and-arts` | 4 | industrial design, product design, visual communication, design history, design education, art theory | [index.md](design-and-arts/index.md) |
| Foreign Languages | `foreign-languages` | 8 | English, linguistics, translation, literature, intercultural communication, language teaching | [index.md](foreign-languages/index.md) |
| Humanities and Social Sciences | `humanities-and-social-sciences` | 7 | humanities, social theory, ethics, political education, culture, philosophy, social development | [index.md](humanities-and-social-sciences/index.md) |
| Information and Electronics | `information-and-electronics` | 43 | signal processing, communications, radar, electronic systems, microwave, image processing, information systems | [index.md](information-and-electronics/index.md) |
| Integrated Circuits and Electronics | `integrated-circuits-and-electronics` | 15 | integrated circuits, microelectronics, semiconductor devices, chip systems, RF circuits, EDA | [index.md](integrated-circuits-and-electronics/index.md) |
| Law | `law` | 24 | civil law, intellectual property, criminal law, international law, administrative law, legal theory, governance | [index.md](law/index.md) |
| Life Science | `life-science` | 20 | biotechnology, biomedical science, bioengineering, molecular biology, neuroscience, biomaterials | [index.md](life-science/index.md) |
| Management | `management` | 44 | innovation management, operations, project management, supply chains, decision science, data-driven management | [index.md](management/index.md) |
| Economics | `economics` | 45 | applied economics, finance, digital economy, industrial economics, regional economics, econometrics | [index.md](economics/index.md) |
| Materials Science and Engineering | `materials-science-and-engineering` | 66 | materials science, nanomaterials, metals, polymers, composites, energy materials, materials processing | [index.md](materials-science-and-engineering/index.md) |
| Mathematics and Statistics | `mathematics-and-statistics` | 6 | applied mathematics, statistics, optimization, probability, differential equations, data analysis | [index.md](mathematics-and-statistics/index.md) |
| Mechanical Engineering | `mechanical-engineering` | 152 | mechanical design, vehicles, engines, manufacturing, machining, tribology, thermal engineering, CAD | [index.md](mechanical-engineering/index.md) |
| Mechatronical Engineering | `mechatronical-engineering` | 51 | mechatronics, intelligent equipment, robotics, sensing, detection, control, unmanned systems | [index.md](mechatronical-engineering/index.md) |
| Optics and Photonics | `optics-and-photonics` | 33 | optics, lasers, photonics, imaging, optical engineering, optoelectronics, spectroscopy | [index.md](optics-and-photonics/index.md) |
| Physics | `physics` | 12 | condensed matter, theoretical physics, quantum physics, optics, plasma, materials physics | [index.md](physics/index.md) |
| Medical Technology | `medical-technology` | 24 | medical robotics, biomedical engineering, rehabilitation, medical imaging, biomaterials, intelligent medicine | [index.md](medical-technology/index.md) |
| Education | `education` | 4 | learning analytics, intelligent tutoring, teacher education, educational psychology, curriculum, pedagogy | [index.md](education/index.md) |

## Research Topic Routing

- Artificial intelligence, machine learning, data mining: start with `computer-science-and-technology/index.md`; also check `automation/index.md`, `information-and-electronics/index.md`, `management/index.md`, and `education/index.md` for applied AI.
- Intelligent tutoring, learning analytics, educational technology: start with `education/index.md`; also check `computer-science-and-technology/index.md` for AI systems, educational games, and software.
- Robotics, control, autonomous systems: start with `automation/index.md`; also check `mechatronical-engineering/index.md`, `mechanical-engineering/index.md`, `aerospace-engineering/index.md`, and `medical-technology/index.md`.
- Computer vision, image processing, signal processing: start with `information-and-electronics/index.md`; also check `computer-science-and-technology/index.md`, `automation/index.md`, `optics-and-photonics/index.md`, and `medical-technology/index.md`.
- Cybersecurity, cryptography, privacy, data security: start with `cyberspace-science-and-technology/index.md`; also check `computer-science-and-technology/index.md` and `law/index.md`.
- Integrated circuits, chips, semiconductors, electronics hardware: start with `integrated-circuits-and-electronics/index.md`; also check `information-and-electronics/index.md` and `optics-and-photonics/index.md`.
- Aerospace, flight, spacecraft, propulsion, guidance: start with `aerospace-engineering/index.md`; also check `automation/index.md` and `mechanical-engineering/index.md`.
- Vehicles, engines, thermal systems, power machinery: start with `mechanical-engineering/index.md`; also check `aerospace-engineering/index.md`, `materials-science-and-engineering/index.md`, and `chemistry-and-chemical-engineering/index.md`.
- Manufacturing, machining, CAD, tribology, mechanical design: start with `mechanical-engineering/index.md`; also check `materials-science-and-engineering/index.md` and `mechatronical-engineering/index.md`.
- Materials, nanomaterials, polymers, composites, energy materials: start with `materials-science-and-engineering/index.md`; also check `chemistry-and-chemical-engineering/index.md`, `physics/index.md`, `optics-and-photonics/index.md`, and `medical-technology/index.md`.
- Chemistry, catalysis, electrochemistry, chemical engineering: start with `chemistry-and-chemical-engineering/index.md`; also check `materials-science-and-engineering/index.md` and `life-science/index.md`.
- Biomedical engineering, medical robotics, rehabilitation, medical imaging: start with `medical-technology/index.md`; also check `life-science/index.md`, `mechanical-engineering/index.md`, and `materials-science-and-engineering/index.md`.
- Optics, lasers, photonics, optoelectronics, spectroscopy: start with `optics-and-photonics/index.md`; also check `physics/index.md`, `information-and-electronics/index.md`, and `integrated-circuits-and-electronics/index.md`.
- Economics, finance, industrial policy, digital economy: start with `economics/index.md`; also check `management/index.md` and `law/index.md`.
- Management, innovation, operations, project management, supply chains: start with `management/index.md`; also check `economics/index.md`.
- Law, governance, intellectual property, data law: start with `law/index.md`; also check `economics/index.md`, `management/index.md`, and `cyberspace-science-and-technology/index.md`.
- Languages, translation, literature, intercultural communication: start with `foreign-languages/index.md`; also check `humanities-and-social-sciences/index.md`.
- Humanities, ethics, philosophy, social science, policy: start with `humanities-and-social-sciences/index.md`; also check `law/index.md`, `economics/index.md`, and `management/index.md`.
- Mathematics, statistics, optimization, probability: start with `mathematics-and-statistics/index.md`; also check `computer-science-and-technology/index.md`, `automation/index.md`, `economics/index.md`, and `management/index.md`.
- Design, product design, visual communication, art theory: start with `design-and-arts/index.md`; also check `mechanical-engineering/index.md` for product/mechanical design and `information-and-electronics/index.md` for interactive systems.

## Ambiguity Rules

- Some professor names and slugs can repeat across departments. Never assume a bare slug such as `zhang-jun`, `liu-yong`, or `qian-kun` identifies one person.
- Use the department-qualified profile ID: `<department-slug>/<professor-slug>`.
- If the user gives only a repeated or ambiguous name, ask which department they mean or show matching candidates.
- If the user asks for a topic with no department, route through the topic list first, then inspect department indexes before opening professor files.

## Coverage Notes

- This corpus covers BIT professor dossier files grouped by department.
- The root index routes; department indexes shortlist; individual professor files prove.
- Department indexes are summaries for navigation, not substitutes for professor dossiers.
- If an index does not contain enough evidence, open the professor file before answering.
- If a dossier contains `## Uncertain or Illegible Text`, keep that uncertainty visible instead of guessing.
- Mechanical Engineering uses the official School of Mechanical Engineering English HTML faculty site; most other departments use ISC poster-style professor pages.
