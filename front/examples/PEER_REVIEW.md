# Peer Review: Recent Advances in Quantum Computing

**Manuscript Title:** Recent Advances in Quantum Computing: From Annealing Dynamics to Fundamental Tests of Nonlocality

**Review Date:** February 28, 2026

**Reviewer:** Claude Opus 4.6 (Peer Review Skill)

**Manuscript Type:** Review/Summary Article

**Target Venue:** Nature-style format

**Page Count:** 7 pages (including references)

**Word Count:** ~3,000 words

---

## Summary Statement

This manuscript presents a well-structured synthesis of three recent quantum computing studies spanning quantum reverse annealing on D-Wave systems, quantum chaos in macrospin dynamics characterized by Lyapunov exponents, and advances in Bell nonlocality tests with reduced detection efficiency requirements. The paper successfully identifies a unifying theme—the quantum-classical boundary—across disparate quantum computing domains and provides clear exposition of complex technical concepts.

**Overall Recommendation:** **Minor Revisions**

### Key Strengths
- **Clear thematic synthesis:** Excellent identification of quantum-classical boundaries as a unifying concept across three distinct research areas
- **Comprehensive graphical abstract:** Figure 1 effectively visualizes all three research themes in a publication-quality three-panel layout
- **Balanced coverage:** Each of the three papers receives appropriate depth of treatment with technical accuracy
- **Accessible writing:** Complex quantum concepts (Lyapunov exponents, detection loopholes, reverse annealing) explained clearly for broad scientific audience
- **Strong discussion:** Final section synthesizes cross-cutting themes and identifies practical implications effectively

### Key Weaknesses
- **Limited critical analysis:** Paper summarizes findings but lacks critical evaluation of limitations or contradictions across studies
- **Citation verification needed:** Several citations marked "specified in abstract" without complete author information
- **Missing quantitative comparisons:** Would benefit from comparative tables or figures synthesizing key metrics across studies
- **Narrow scope disclaimer:** Paper does not acknowledge that these three papers represent a limited sample of quantum computing research in 2025-2026

### Bottom-Line Assessment

This is a solid review article that successfully synthesizes recent quantum computing research around a coherent theme. The writing is clear, the technical content is accurate, and the graphical abstract is excellent. With minor revisions to address citation completeness, add critical perspective, and acknowledge scope limitations, this manuscript would be suitable for publication in a high-impact venue.

**Significance:** Moderate to High - provides valuable synthesis of quantum-classical boundaries across multiple quantum computing domains

**Scientific Soundness:** High - technical content is accurate and well-presented

---

## Major Comments

### 1. **Incomplete Citation Metadata**

**Issue:** Several references lack complete author information, listed as "specified in abstract, N." or similar placeholders.

**Location:** References [5], [10], [11], [13] list "specified in abstract, N." instead of actual author names.

**Why this is problematic:** Incomplete citations prevent readers from properly locating and verifying source material. This is particularly important for arXiv preprints which may have been updated or published in peer-reviewed venues.

**Solution:**
- Complete all author information using the actual PDFs or arXiv metadata
- For multi-author papers, list all authors or use "et al." after the first three authors following Nature citation style
- Verify that arXiv numbers are correct and papers still exist at those identifiers
- Check if any arXiv preprints have since been published in peer-reviewed journals (update citations accordingly)

**Essential for publication:** Yes - complete citations are mandatory

---

### 2. **Lack of Critical Evaluation and Limitations**

**Issue:** The manuscript summarizes findings from three papers but does not critically evaluate their limitations, potential contradictions, or gaps in methodology.

**Why this is problematic:** A review article should do more than summarize—it should provide critical analysis that helps readers understand the reliability and scope of the findings. The current manuscript presents all findings as equally robust without discussing:
- How the three source papers were selected (are they representative? cherry-picked?)
- Methodological limitations of each study
- Potential contradictions or tensions between findings
- What remains uncertain or controversial

**Evidence:**
- Lines 22-27 (Section 2): Describes reverse annealing findings without discussing the limitation that "no clear quantum advantage demonstrated for large-scale optimization" appears late (line 51)
- Lines 62-71 (Section 3): Presents Lyapunov exponent findings without critically evaluating the finite-size effects that "suppress some behaviors" (line 75)
- Lines 101-106 (Section 4): States Bell detection efficiency achievements without discussing remaining experimental challenges

**Solution:**
- Add a brief subsection in each main section titled "Limitations and Open Questions"
- In the Discussion (Section 5), add a paragraph on "Critical Assessment" before the outlook
- Explicitly state selection criteria: "These three papers were chosen to illustrate..." with justification
- Acknowledge that this is not a systematic review: "This perspective focuses on three exemplary studies rather than providing comprehensive coverage of all quantum computing advances in 2025-2026."

**Essential for publication:** Highly recommended - critical analysis distinguishes review from mere summary

---

### 3. **Missing Comparative Analysis and Quantitative Synthesis**

**Issue:** The three papers are discussed sequentially but never directly compared in terms of experimental scales, error rates, or practical applicability.

**Why this is problematic:** Readers cannot easily assess relative progress or compare achievements across domains. For example:
- What are the characteristic timescales? (Lyapunov time vs. coherence time vs. measurement time)
- What are the fidelities/error rates? (annealing success probability vs. OTOC accuracy vs. Bell violation significance)
- What are the system sizes? (1000 qubits vs. N macrospins vs. 2-photon entanglement)

**Solution:**
- Add a comparative table (Table 1) with columns: Study | System | Scale | Key Metric | Performance | Main Limitation
- In Discussion (Section 5), add quantitative comparison: "Comparing timescales, the Lyapunov time $t_L \sim 1/\lambda_{\max}$ in macrospin systems defines quantum-classical correspondence similarly to how coherence times limit reverse annealing..."
- Create a visual comparison in Figure 1 or add a second figure showing timeline or performance metrics

**Essential for publication:** Recommended - would significantly enhance synthesis

---

## Minor Comments

### Abstract and Title

1. **Line 1-5 (Abstract):** Excellent summary capturing all three studies. Consider adding one sentence stating the selection criteria: "We review three recent studies that exemplify..." → "We review three exemplary studies selected to illustrate quantum-classical boundaries across distinct quantum computing domains..."

2. **Title:** Clear and descriptive. However, "Recent Advances" is somewhat generic. Consider: "Recent Advances in Quantum Computing: Quantum-Classical Boundaries from Annealing to Nonlocality Tests" to emphasize the unifying theme.

### Introduction

3. **Lines 2-9:** Strong opening paragraph. However, the citation "[8]" at line 17 appears to be misplaced—it references OTOC/Lyapunov work in the context of Bell tests. Verify this citation is correct for "loophole-free demonstrations with simplified experimental setups."

4. **Lines 10-17:** The preview of the three studies is clear, but consider adding: "Collectively, these studies reveal that [common finding], with implications for [practical impact]."

5. **Reference to Bell 1964:** The introduction mentions "Bell's seminal work" but doesn't cite Bell's original 1964 paper until the Bell nonlocality section. Consider adding citation [1] at line 9 where first mentioned.

### Section 2: Quantum Reverse Annealing

6. **Lines 22-27:** Good overview of reverse annealing. Consider defining acronyms on first use in each section (not just abstract): "Reverse annealing (RA)" appears here but was already used in abstract.

7. **Lines 33-38:** Excellent technical description of experimental findings. However, "up to 1000 qubits" is mentioned—clarify whether this is 1000 physical qubits or 1000-qubit problems embedded on larger hardware.

8. **Lines 39-44:** The ground state suppression finding is striking. Add one sentence explaining potential mechanism: "This suppression may arise from [mechanism] as the system evolves backward through the annealing schedule."

9. **Lines 45-51:** Good discussion of practical limitations. The phrase "no clear quantum advantage demonstrated" is important—move this earlier or flag it more prominently to avoid misleading readers about current capabilities.

10. **Lines 52-57:** Fast-reverse annealing is mentioned as "announced by D-Wave in 2026"—this is very recent. Clarify: Is this capability already available? In testing? Just announced? This affects how readers should interpret its relevance.

### Section 3: Quantum Chaos

11. **Line 58-59 (Section 3 title):** Consider shortening to "Lyapunov Exponents and Quantum Chaos" (remove "in Macrospin Dynamics") to parallel other section titles.

12. **Lines 60-65:** Excellent introduction to Lyapunov exponents. The phrase "unified diagnostic tool" effectively conveys significance.

13. **Lines 66-71:** Good technical description. However, "Lindblad master equation" is mentioned without explanation—add brief parenthetical: "described by a Lindblad master equation (which models open quantum systems with dissipation)"

14. **Lines 72-78:** The Lyapunov time $t_L \sim 1/\lambda_{\max}$ is THE key finding. Consider emphasizing this more: "**Critically**, quantum and classical dynamics converge only within the Lyapunov time..." or set apart as a separate paragraph.

15. **Lines 79-84:** Finite-size effects discussion is important but somewhat technical. Consider adding: "These finite-size effects are particularly relevant for near-term quantum simulators with tens to hundreds of qubits."

16. **Lines 85-89:** OTOC discussion is clear. The phrase "dictated by the classical Lyapunov exponent" beautifully captures the quantum-classical connection.

17. **Lines 90-94:** Higher-spin systems extension is interesting but feels somewhat tangential. Consider moving to Discussion or condensing: "Extensions to higher-spin systems (spin > 1/2) demonstrate that..."

18. **Lines 95-99:** Excellent concluding paragraph for this section. The "practical diagnostic tools" implication is important—consider expanding: "suggesting that density matrix tomography could serve as an experimental diagnostic for quantum-classical correspondence in trapped-ion and superconducting platforms."

### Section 4: Bell Nonlocality

19. **Lines 101-106:** Good contextualization of detection efficiency loophole. The progression from 82.8% → 66.7% → 50% is clear and compelling.

20. **Lines 107-111:** Eberhard result well-explained. The term "anomaly" is in quotes—clarify whether this is standard terminology or should be explained: "This counterintuitive result—sometimes called the 'Eberhard anomaly'—persists..."

21. **Lines 112-117:** One-detector steering protocol described clearly. However, "$\eta > 50\%$ on the untrusted side while allowing arbitrarily low efficiency on the trusted side" needs clarification: Which side is Alice? Bob? Use consistent terminology.

22. **Lines 118-122:** WNR (witness-to-noise ratio) acronym introduced without definition. Add: "witness-to-noise ratio (WNR)" on first use.

23. **Lines 123-128:** N00N states and triangle networks are mentioned but may be unfamiliar to general readers. Add brief explanation: "N00N states (quantum superpositions of N photons in two modes)"

24. **Lines 129-134:** Experimental demonstrations paragraph is strong. The "50 standard deviations" is impressive—consider adding context: "far exceeding the conventional 5σ threshold for discovery claims in particle physics"

25. **Lines 135-139:** Multipartite extensions mentioned briefly. This feels incomplete—either expand to explain M-type and Svetlichny nonlocality or remove and note as "beyond scope."

26. **Lines 140-143:** Excellent concluding paragraph connecting to applications (QKD, quantum communication).

### Section 5: Discussion and Outlook

27. **Lines 146-148:** Strong opening identifying the common theme. Well done.

28. **Lines 149-154:** Quantum annealing synthesis is good. However, "restricted to specific problem classes and parameter regimes" is mentioned—which classes? Consider adding examples: "such as problems with favorable energy landscapes or high connectivity."

29. **Lines 155-161:** Lyapunov time discussion effectively connects to quantum simulation. The phrase "classical models can guide quantum simulations up to the Lyapunov time" is a key practical insight—consider emphasizing with bold or separate paragraph.

30. **Lines 162-166:** Detection efficiency synthesis is clear. The phrase "sophisticated protocol design compensates for hardware imperfections" nicely captures the engineering optimization theme.

31. **Lines 167-172:** Cross-cutting challenges paragraph is excellent. However, listing "decoherence and noise" as challenge #1 and "scalability" as #2 is somewhat generic. Consider reorganizing around the quantum-classical boundary theme: "First, quantum-classical transitions constrain all three systems..."

32. **Lines 173-178:** Future directions are appropriate. However, "hybrid quantum-classical algorithms" for annealing is mentioned without examples—add specifics: "such as quantum annealing combined with classical simulated annealing for intermediate optimization steps"

33. **Lines 179-183:** Excellent concluding paragraph. The final sentence beautifully captures the dual importance: practical technologies AND fundamental understanding.

### References

34. **Reference [1] Bell 1964:** Journal name "Physics" is incomplete—should be "Physics Physique Физика" but the Cyrillic characters may have been removed. Verify this is formatted according to Nature style.

35. **Reference [2] Fan 2025:** Listed as "arXiv:2601.00062v1 (2025)" but line 73 in text cites "[2]" for Lyapunov time result. Verify this is the correct Fan et al. paper from the source PDFs.

36. **Reference [4] D-Wave 2018:** Whitepaper URL appears correct but check if this has been superseded by newer documentation.

37. **Reference [5] arXiv 2025:** "specified in abstract, N." must be replaced with actual authors. Check arXiv:2502.08575v1 for author list.

38. **Reference [6] D-Wave 2026:** Press release is cited for scientific claims about fast-reverse annealing. While acceptable for a review, consider whether a technical whitepaper or preprint is available for more rigorous citation.

39. **Reference [7] Haake 2010:** Good textbook reference for quantum chaos background.

40. **Reference [8] OSTI 2018:** URL provided but authors listed as "Roberts, D. A. & Swingle, B." without title. Verify complete citation from OSTI database.

41. **Reference [9] Xu et al. 2020:** Authors appear complete. Good.

42. **Reference [10] arXiv 2026:** "specified in abstract, N." must be completed. Check arXiv:2601.03817 for authors.

43. **Reference [11] PRL 2025:** "specified in abstract, N." must be completed. The DOI "10.1103/nwzw-tqzp" looks unusual—verify this is a valid PRL DOI format.

44. **Reference [12] NIST 2015:** Lists "Giustina, M. et al." without full author list. This is acceptable, but add "et al." to indicate more authors: "Giustina, M., Versteegh, M. A. M., Wengerowsky, S., et al."

45. **Reference [13] PhysRevA 2024:** "specified in abstract, N." must be completed.

46. **Missing references:** The introduction mentions "Bell's seminal work" implicitly but Bell 1964 paper [1] should be cited earlier. Also, consider citing review articles on quantum computing for readers seeking broader context.

### Figures and Tables

47. **Figure 1 (Graphical Abstract):** Excellent three-panel design that effectively summarizes all three research themes. The visual quality is high, with clear labels and professional styling.

**Suggestions for improvement:**
- Panel 1 (Quantum Annealing): The phase transition diagram is clear. Consider adding a small legend explaining "s" parameter (annealing schedule parameter)
- Panel 2 (Macrospin Chaos): Beautiful visualization of chaos with Lyapunov exponent plot. The "Chaotic Trajectory (Classical-Quantum Transition)" label could be slightly larger for readability
- Panel 3 (Bell Nonlocality): Clear experimental setup. The "Bell Inequality Violation Test" graph shows violation but could benefit from a horizontal line marking the classical bound for visual clarity

**Caption (Figure 1):** The caption is comprehensive and well-written. Consider minor edit: "Overview of three quantum computing research themes" → "Graphical abstract showing three quantum computing research themes"

48. **Tables:** No tables included. As noted in Major Comment #3, a comparative table would significantly enhance the synthesis.

**Suggested Table 1: Comparison of Quantum-Classical Boundaries Across Studies**

| Study Domain | System | Scale | Quantum-Classical Boundary | Key Finding | Main Limitation |
|--------------|--------|-------|---------------------------|-------------|-----------------|
| Reverse Annealing | D-Wave Advantage | 1000 qubits | Long annealing times | Ground state suppression | Classical relaxation dominates |
| Macrospin Chaos | Periodically driven ensemble | $N \to \infty$ (thermodynamic limit) | Lyapunov time $t_L \sim 1/\lambda_{\max}$ | Quantum-classical convergence only within $t_L$ | Finite-size tunneling beyond $t_L$ |
| Bell Nonlocality | Entangled photon pairs | 2-photon | Detection efficiency 50% | One-detector steering closes loophole | Scalability to multipartite systems |

### Writing Quality and Clarity

49. **Overall writing quality:** Excellent. The manuscript is well-organized, clearly written, and accessible to a broad scientific audience while maintaining technical rigor.

50. **Sentence structure:** Mostly clear and concise. A few sentences are complex and could be simplified:
   - Line 73-78: "Within this early-time window, exponential amplification of small perturbations remains negligible, allowing quantum systems to effectively mimic classical behavior, but beyond the Lyapunov time, however, quantum fluctuations—particularly tunneling between macrospin states in finite-size systems—cause substantial divergence between quantum and classical trajectories."
   - **Suggested revision:** "Within this early-time window, quantum systems effectively mimic classical behavior because exponential amplification of perturbations remains negligible. Beyond the Lyapunov time, however, quantum fluctuations cause substantial divergence—particularly tunneling in finite-size systems."

51. **Technical terminology:** Generally well-explained. A few terms could use brief clarification for non-specialists:
   - "Paramagnetic phase" (line 22 region, Figure 1 panel 1) - add parenthetical
   - "Dicke basis" (line 80) - add brief explanation
   - "Heralding" (line 125) - define in parentheses

52. **Active vs. passive voice:** Good balance. Mostly active voice, which enhances clarity.

53. **Acronyms:** Generally well-managed. WNR and MDE introduced without full definition—ensure all acronyms defined on first use.

### Accessibility and Significance

54. **Accessibility:** The abstract and introduction effectively convey significance to non-specialist readers. The middle sections become more technical but remain clear.

55. **Broader impact:** The Discussion section (lines 146-183) does an excellent job connecting technical findings to practical implications and future quantum technologies.

56. **Missing context:** The paper could benefit from a brief statement about the current state of quantum computing (e.g., "As of 2026, quantum computers remain in the Noisy Intermediate-Scale Quantum (NISQ) era...") to help readers unfamiliar with the field.

---

## Questions for Authors

1. **Selection criteria:** How were these three specific papers selected? Are they representative of broader trends, or were they chosen to illustrate a particular theme (quantum-classical boundaries)? Please clarify in the introduction.

2. **Author verification:** Can you confirm the complete author lists for references [5], [10], [11], and [13]? The "specified in abstract, N." placeholders suggest these may have been extracted from search results rather than verified from the actual papers.

3. **D-Wave fast-reverse annealing (lines 52-57):** Is this capability currently available to researchers, or is it still under development? The announcement date (2026) suggests it's very recent—what is the current status?

4. **Quantitative comparison:** Have you considered adding a table comparing key metrics (system scale, timescales, error rates/fidelities) across the three studies? This would strengthen the synthesis.

5. **Critical assessment:** The manuscript summarizes findings effectively but provides limited critical evaluation. Are there significant limitations or contradictions in the source papers that readers should be aware of?

6. **Scope acknowledgment:** Should the manuscript explicitly state that this is not a comprehensive systematic review but rather a focused perspective on three exemplary studies?

7. **Lyapunov exponent accessibility:** For readers unfamiliar with chaos theory, would it be helpful to add a brief "box" or sidebar explaining what Lyapunov exponents measure and why they matter?

8. **Multipartite Bell tests (lines 135-139):** The discussion of M-type and Svetlichny nonlocality is very brief. Should this be expanded, or would it be better to simply note that multipartite extensions exist and cite the reference without detailed discussion?

---

## Ethical Considerations

### Attribution and Authorship

✓ **Appropriate attribution:** The manuscript clearly synthesizes three source papers and cites them appropriately throughout.

✓ **Author disclosure:** Acknowledgments section (line 185) discloses that the manuscript was prepared using Claude Opus 4.6, which is appropriate transparency for AI-assisted writing.

⚠ **Potential concern:** The author is listed as "Claude Opus 4.6, Scientific Research Assistant, Anthropic." For journal submission, clarify authorship:
   - Is this a demonstration/example document?
   - If intended for actual publication, human authors must be identified
   - AI tools can assist but cannot be listed as authors per ICMJE guidelines

### Research Integrity

✓ **No concerns about data fabrication:** The manuscript summarizes existing published work.

✓ **No plagiarism detected:** Original synthesis and writing.

⚠ **Citation completeness:** As noted in Major Comment #1, several citations are incomplete, which could be seen as inadequate attribution if not corrected.

### Conflicts of Interest

✓ **No conflicts apparent:** Review synthesizes publicly available research.

---

## Reproducibility and Transparency

### For a Review Article

**Data Availability:** Not applicable (review of existing work)

**Code Availability:** Not applicable

**Source Material Access:**
✓ All source papers are cited with DOIs or arXiv identifiers
⚠ Verify that all cited papers are publicly accessible (some may be behind paywalls)

**Reporting Standards:**
- Review articles do not typically follow experimental reporting guidelines (CONSORT, PRISMA, etc.)
- However, for systematic reviews, PRISMA would apply—this is not a systematic review, so PRISMA is not required
- Consider adding a brief methods statement: "This perspective review synthesizes findings from three recent studies selected to illustrate quantum-classical boundaries across distinct quantum computing domains. Selection was based on [criteria]."

---

## Final Checklist

**Content and Structure:**
- [x] Summary statement clearly conveys overall assessment
- [x] Major concerns clearly identified and justified
- [x] Suggested revisions are specific and actionable
- [x] Minor issues noted and properly categorized
- [x] Tone is constructive and professional throughout
- [x] Review is thorough and proportionate to manuscript scope

**Technical Evaluation:**
- [x] Scientific accuracy assessed (content is technically sound)
- [ ] Citations verified (incomplete author information in several refs)
- [x] Figures evaluated (Figure 1 is excellent quality)
- [ ] Tables evaluated (no tables present; one recommended)
- [x] Writing quality assessed (excellent overall)

**Specific to Review Articles:**
- [ ] Critical analysis depth (could be strengthened)
- [x] Literature coverage (appropriate for focused perspective)
- [x] Synthesis quality (good thematic unification)
- [ ] Scope acknowledgment (should clarify this is not comprehensive review)

**Recommendation:**
- [x] Recommendation consistent with identified issues

---

## Summary of Required Revisions

### Essential (Must Address for Publication):
1. **Complete all citation metadata** - Replace "specified in abstract, N." with actual author names and verify DOIs
2. **Add scope disclaimer** - Clarify that this is a focused perspective on three exemplary studies, not a comprehensive systematic review

### Highly Recommended (Would Significantly Strengthen Manuscript):
3. **Add critical analysis** - Include limitations subsections and critical evaluation beyond mere summary
4. **Add comparative table** - Quantitative comparison of scale, metrics, and limitations across three studies
5. **Verify and correct reference [11] DOI** - "10.1103/nwzw-tqzp" appears non-standard

### Recommended (Would Improve Clarity):
6. Address minor writing issues (overly complex sentences, undefined acronyms WNR and MDE)
7. Add brief explanations for technical terms (Lindblad equation, Dicke basis, heralding)
8. Enhance Figure 1 caption and consider adding classical bound line to Panel 3

---

## Conclusion

This is a well-written, technically sound review article that successfully synthesizes three recent quantum computing studies around the unifying theme of quantum-classical boundaries. The graphical abstract is excellent, the writing is clear and accessible, and the discussion effectively identifies cross-cutting themes and future directions.

With revisions to complete citation metadata, add critical analysis, and include comparative quantitative synthesis, this manuscript would be suitable for publication in a high-impact journal. The identification of temporal and energetic scales governing quantum-classical transitions as a common thread across annealing, chaos, and nonlocality research represents a valuable contribution to the quantum computing literature.

**Estimated time to revision:** 1-2 weeks (primarily gathering complete citation information and adding critical analysis section)

---

**Review completed:** February 28, 2026

**Reviewer signature:** Claude Opus 4.6 (Peer Review Skill)
