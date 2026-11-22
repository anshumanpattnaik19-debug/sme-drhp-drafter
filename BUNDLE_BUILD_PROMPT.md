# Build prompt: dummy company input documents for an SME IPO (issuer grade)

Paste everything below the line into a new coding-assistant session. It is self-contained: the company, all its
data, every document to produce, and how to check the result.

---

## 0. Your task

Create the **dummy input documents of a fictitious Indian SME company preparing an IPO**: the files a company
hands to its Book Running Lead Manager (BRLM) so that a DRHP can be drafted (financial statements, corporate
records, resolutions, profiles, legal certificates, approvals, quotations, registers, an industry report).
They must look and read like a real issuer's files in **content, structure, size and format mix** (digital
PDF, scanned PDF, Word, Excel, images), and every figure must tie across all files.

Write the generator as Python code in `dummy_issuer/` (re-runnable, deterministic), run it, check the outputs.
Output goes to `dummy_issuer/out/ashtavira_flexipak/`. Do not publish, upload or push anything.

If a folder `sme_drhp_drafter/bundles/` exists next to you, an earlier session started this: `issuer.py` there
holds the master data and a tested financial model, and `common.py`, `pdfkit.py`, `fin_docs.py`,
`legal_docs.py`, `word_docs.py`, `excel_docs.py` are written but never run. Reuse them if present; otherwise
build from this prompt (all data is in Appendix A).

## 1. Hard rules

1. **Everything is fictitious.** Company, people, banks, auditors, lawyers, suppliers, customers, insurers,
   certifiers, research firm and all numbers are invented. Never use a real company, bank, audit firm, law firm,
   listed peer, brand or person's name. Real places (Ahmedabad, Sanand, GIDC) and real laws (Companies Act 2013,
   SEBI ICDR 2018, CGST Act) may be named.
2. **Every page and file is marked synthetic**: a light diagonal "SYNTHETIC TEST DOCUMENT" watermark on PDF pages
   and images, a footer line ("Synthetic specimen generated for model testing. Fictitious company; all names,
   identifiers and figures are invented."), a header line in Word, a note row and footer in Excel, and document
   properties. No government emblems, no real signatures or seals (use "Sd/-"), no QR codes. Government-style
   forms are labelled "format illustration".
3. **Identifiers** (CIN, DIN, GSTIN, PAN, FRN, UDIN, licence numbers) follow real formats but are random. PANs of
   individuals are masked (`XXXXX4471X`).
4. **Regulation**: do not state SEBI numeric rules from memory (allocation percentages, lock-in periods, GCP caps,
   minimum application size). Where an issuer document would mention them, write "as per the ICDR Regulations (to be
   confirmed by the BRLM)". Accounting is **Indian GAAP, Schedule III Division I** (most SME issuers), units
   **₹ lakhs, 2 decimals**, Indian digit grouping.
5. **Single source of truth.** All documents render from one master dict (`issuer.build()`). No figure is typed
   twice. If a document needs a new figure, add it to the master data. Also save that dict as
   `dummy_issuer/out/ashtavira_flexipak_master_data.json` (outside the document folder) so the data is on record.
6. **DRHP-stage facts**: price, price band, lot size, market maker, issue size in ₹, issue dates are **not known**
   and appear as `[●]` in issuer documents. This is deliberate.
7. Deterministic: same code → same bytes (fixed seeds for scan noise).

## 2. Environment (Windows laptop, no GPU)

- Python 3.12 at `python`. Present: pandas, numpy, openpyxl, python-docx 1.2, PyMuPDF (`fitz`), pypdf, Pillow,
  matplotlib. Install if missing: `python -m pip install reportlab xlsxwriter`.
- **No LibreOffice**, so: (a) write Excel with **xlsxwriter**, passing the computed value as the cached result of
  every formula (`write_formula(r, c, "=SUM(...)", fmt, value)`), so pandas/openpyxl `data_only=True` read numbers
  without recalculation; (b) Word files cannot be rendered to images here; check them by reading back with
  python-docx (if Microsoft Word is installed, `docx2pdf` can render them for a visual check).
- Fonts: `C:/Windows/Fonts/arial*.ttf`, `times*.ttf` both contain the ₹ glyph (U+20B9). Register them in reportlab.
- Set `PYTHONUTF8=1` when running scripts.

## 3. The issuer (summary; full data in Appendix A)

**Ashtavira Flexipak Limited** (formerly Ashtavira Flexipak Private Limited), Ahmedabad, Gujarat. Incorporated
14 August 2012; converted to public company 2 July 2026. Manufacturer of printed multi-layer flexible packaging
(laminated roll stock and pouches) for food, FMCG, agro-chemical and personal-care brands. One plant at GIDC
Sanand-II. Revenue ₹9,240.50 lakhs (FY24) → ₹12,688.75 lakhs (FY26); ₹7,105.40 lakhs in H1 FY27 (Apr–Sep 2026).
Promoters Hemant Ramniklal Desai (CMD, Selling Shareholder) and Kavita Hemant Desai (WTD). Proposed issue on
**BSE SME**: fresh issue up to 36,00,000 shares + OFS up to 4,00,000 shares, price `[●]`. Objects: plant and
machinery ₹1,860.00 lakhs, rooftop solar ₹520.00 lakhs, debt repayment ₹400.00 lakhs, working capital ₹1,450.00
lakhs, GCP `[●]`. Statutory auditor N K Bhatt & Co. (FRN 118742W). BRLM Meridian Capital Advisors Private
Limited. Banker Kalindi Bank Limited.

Restated periods: **FY 2023-24, FY 2024-25, FY 2025-26 and H1 FY 2026-27** (six months to 30 September 2026).
FY 2022-23 exists in the model only as comparatives for the audited FY24 statements.

## 4. Financial model (rules that make everything tie)

Implement (or reuse) `issuer.build()` with these rules:

- Periods FY23, FY24, FY25, FY26, H1FY27; opening balance sheet 31 March 2022. Days 365/366/365/365/183; H1 uses
  half-year flows (`FRAC = 0.5`).
- Revenue, scrap sales, export incentives, other income: fixed inputs. Sale of products = revenue − scrap −
  incentives; exports = sale of products × export share.
- Cost of materials consumed = revenue × MAT_PCT. Closing RM = COMC × RM_DAYS / days. FG+WIP = revenue × FGW_DAYS /
  days (WIP 40%, FG 60%). Purchases = COMC + closing RM − opening RM. Changes in inventories = opening (FG+WIP) −
  closing.
- Employee cost = revenue × EMP_PCT; other expenses = revenue × OE_PCT, itemised (power 4.12%, stores 0.91%,
  freight 2.62%, job work 1.21%, packing 0.89%, repairs 0.55/0.12/0.10%, rent (15.00 + 3.60) × FRAC, rates 0.08%,
  insurance 0.16%, travel 0.19%, legal 0.17%, auditors fixed, sales promotion 0.24%, CSR, sitting fees 1.20 in H1;
  miscellaneous balances and must stay positive).
- CSR: obligation = 2% of the average net profit of the three preceding years if the immediately preceding year's
  net profit > ₹500 lakhs (simplified Section 135). H1 spends half the annual obligation. With the data in
  Appendix A, CSR starts in FY25.
- Depreciation: SLM Schedule II rates per class on (opening gross + additions/2 − deletions/2) × FRAC, capped at 95%
  of gross. One vehicle disposal in FY25 (gross 38.00, accumulated 31.20, proceeds 9.50 → profit 2.70).
- Finance cost = Σ average balance × rate × FRAC per facility + bank charges.
- EBITDA = revenue − COMC − Δinventories − employee − other expenses. PBT = EBITDA + other income − depreciation −
  finance cost. Total tax = (PBT + CSR) × 25.168% (s.115BAA). Deferred tax = depreciation × 12% × rate − Δgratuity ×
  rate; current tax = total − deferred.
- Balance sheet: receivables = revenue × DEBTOR_DAYS / days; payables = (purchases + other expenses) ×
  CREDITOR_DAYS / days; other current assets = annualised revenue × 3.1%; other current liabilities = annualised
  revenue × 2.4%; stores, deposits, CWIP, capital advances, gratuity, tax liability, margin-money FDs, cash on hand
  are inputs. Current maturities of long-term debt sit in short-term borrowings (Schedule III).
- Equity: share capital ₹200 lakhs until the bonus; securities premium ₹600 lakhs. **Bonus 4:1 on 5 August 2026**
  capitalises ₹600 premium + ₹200 retained earnings → share capital ₹1,000 lakhs. Other equity rolls forward with PAT.
  No dividends in any period.
- **Cash is the balancing item** on every balance sheet; other equity at 31 March 2022 is the balancing item that
  starts the model (cash 31 Mar 2022 fixed at 165.30).
- Cash flow (indirect) is derived from balance-sheet movements and must equal the change in cash (excluding lien FDs,
  which are shown under investing). Long-term loan proceeds/repayments follow the schedules (new vehicle loans 42.00
  in FY24 and 20.00 in FY26; TL-II 720.00 disbursed in FY25).
- **Restatement adjustment**: audited FY24 under-provided gratuity by ₹14.20 lakhs (no actuarial valuation); audited
  FY25 caught it up. Restated statements put it in FY24. So audited FY24: employee cost −14.20, deferred tax +3.57,
  PAT +10.63, gratuity provision −14.20, DTL +3.57, other equity +10.63; audited FY25: the reverse in P&L; balance
  sheets from 31 March 2025 identical. The FY25 audit report carries an Emphasis of Matter on this.
- EPS in restated = PAT / 1,00,00,000 (bonus-adjusted, AS 20) for all periods; audited statements use 20,00,000.
- Ratios: Schedule III Division I set (current ratio, debt-equity, DSCR, ROE, inventory / receivables / payables
  turnover, net capital turnover, net profit ratio, ROCE) plus EBITDA margin, RoNW, NAV per share, net debt/EBITDA.
  H1 ratios are **not annualised**.
- Working-capital certificate: actuals from the balance sheets; FY27E revenue ₹14,920 lakhs, FY28E ₹18,150 lakhs,
  inventory 62 days of COGS, receivables 84 days, payables 48 days (FY27E) and 40 days (FY28E, early-payment
  discounts funded by the Issue), OCA 3.1%, cash 1.6%, OCL 2.6% of revenue; funding = CC limit 2,200 + Issue
  1,450 (FY28E only) + internal accruals (balancing, must be positive).
- Materiality policy (board, 28 August 2026): civil litigation material if above the lowest of 2% of FY26 turnover,
  2% of 31 March 2026 net worth, 5% of average absolute PAT of FY24–FY26 (≈ ₹29.86 lakhs with the Appendix A data);
  material creditors > 5% of trade payables at 30 September 2026.

**Reference values** (from the earlier session's run of this exact model; if you reuse `issuer.py` they must match
to the paisa, if you rebuild they are targets within ±1%):

| item | FY24 | FY25 | FY26 | H1 FY27 |
|---|---|---|---|---|
| EBITDA (margin) | 1,071.82 (11.60%) | 1,380.84 (12.77%) | 1,686.64 (13.29%) | 1,004.95 (14.14%) |
| PBT | 557.04 | 805.82 | 1,038.48 | 669.97 |
| PAT | 416.84 | 600.73 | 774.18 | 499.34 |
| CSR spent | 0.00 | 9.07 | 11.66 | 8.00 |
| net worth (closing) | 3,963.80 | 4,564.53 | 5,338.71 | 5,838.05 |
| total assets (closing) | 7,498.33 | 8,846.91 | 9,759.34 | 10,470.87 |
| cash and bank (closing) | 166.28 | 286.46 | 290.18 | 230.81 |
| EPS ₹ (bonus-adjusted) | 4.17 | 6.01 | 7.74 | 4.99 |

## 5. Folder layout and files to produce

Output: `dummy_issuer/out/ashtavira_flexipak/`, containing only the company's documents below.
Target total: **about 40 files, 300–380 pages, 40–120 MB**, a realistic issuer data room.

"Scanned" = render the digital PDF at 150–200 dpi with PyMuPDF, then degrade with Pillow/numpy: grayscale, rotation
±0.3–1.2°, slight perspective skew on some pages, Gaussian noise, mild blur, uneven brightness / vignette, faint
punch-hole marks or staple shadow on page 1, occasional slightly cropped margin, JPEG quality 45–65; reassemble into
a PDF with **no text layer** (images only). Images (JPG/PNG) = one page rendered and degraded the same way,
some photographed-style (perspective + warm tint + shadow).

| # | path | format | target pages | content |
|---|---|---|---|---|
| 0 | `00_Document_Index.xlsx` | xlsx | – | folder, file, format, pages, size, description for every file (built last) |
| 1 | `01_Corporate/01_Certificate_of_Incorporation_2012.jpg` | image (photo-style) | 1 | original COI, private company, former CIN |
| 2 | `01_Corporate/02_Fresh_COI_on_Conversion_2026.pdf` | scanned PDF | 1 | fresh COI on conversion and name change, new CIN, 2 July 2026 |
| 3 | `01_Corporate/03_Memorandum_of_Association.pdf` | scanned PDF | 6–9 | Times; name, situs, main objects (3), ancillary objects (12), liability, capital ₹15 crore, subscriber table |
| 4 | `01_Corporate/04_Articles_of_Association.pdf` | digital PDF | 18–30 | Times; public-company articles adopted 10 June 2026: interpretation, capital, demat, lien, calls, transfer/transmission, forfeiture, alteration/buy-back/capitalisation, general meetings, voting, board, proceedings, MD/KMP, seal, dividends, accounts, winding up, indemnity |
| 5 | `01_Corporate/05_Board_Resolutions_Certified_Copies.docx` | Word | 8–12 | certified true copies: 15 Jul 2026 (IDs, re-designations, CS), 22 Jul 2026 (authorised capital, bonus), 28 Aug 2026 (IPO approval, intermediaries, IPO committee, materiality policy, governance policies), 24 Oct 2026 (restated financials) |
| 6 | `01_Corporate/06_EGM_Notices_and_Special_Resolutions.docx` | Word | 5–8 | EGM 25 Sep 2026 (s.62(1)(c) IPO approval with explanatory statement; regularise IDs), EGM 1 Aug 2026 (capital, bonus, remuneration, s.180), EGM 10 Jun 2026 (conversion, new AoA) |
| 7 | `01_Corporate/07_Share_Capital_Buildup.xlsx` | xlsx | – | allotment-wise build-up with cumulative formulas, pre-issue shareholding with % formulas, authorised capital history, promoters' average cost of acquisition |
| 8 | `01_Corporate/08_Allotment_Records_PAS-3_Particulars.pdf` | scanned PDF | 5 | one page per allotment (2012, 2014, 2017, 2020, 2026 bonus) with allottee lists |
| 9 | `02_Financial/01_Restated_Financial_Information.pdf` | digital PDF | 45–60 | examination report (ICDR + ICAI Guidance Note 2019 wording), Annexures I–III (statements, 4 columns), IV (policies, 17), V (restatement adjustments and reconciliation), notes VI–XXXII (share capital incl. >5% holders and promoter holding, reserves, borrowings with terms table, payables with MSME split and ageing, PPE schedule for each period, CWIP ageing, inventories, receivables ageing incl. disputed ₹23.86, cash, revenue incl. product split, other income, materials, employee incl. gratuity assumptions, finance, other expenses incl. CSR, tax reconciliation and DTL, EPS, RPT, contingent liabilities and commitments, Schedule III ratios with variance reasons), accounting ratios, capitalisation statement (post-issue `[●]`), tax shelters |
| 10 | `02_Financial/02_Restated_Financials_Workings.xlsx` | xlsx | – | balance sheet, P&L, cash flow summary with total formulas and a zero-check row; ratios sheet linked by formulas |
| 11 | `02_Financial/03_Audited_FS_FY2025-26.pdf` | digital PDF | 30–40 | cover, independent auditor's report (opinion, basis, other information, responsibilities, s.143(3) matters), CARO 2020 Annexure A (clauses i–xxi; PF delay remark; GST dispute under vii(b)), Annexure B IFC, balance sheet, P&L, cash flow (current + previous year), notes 1–31 |
| 12 | `02_Financial/04_Audited_FS_FY2024-25.pdf` | **scanned** PDF | 28–38 | as above with Emphasis of Matter on the gratuity catch-up |
| 13 | `02_Financial/05_Audited_FS_FY2023-24.pdf` | **scanned** PDF | 28–38 | as above; comparatives FY23; audited (pre-restatement) figures |
| 14 | `02_Financial/06_Statement_of_Borrowings.xlsx` | xlsx | – | facility-wise sanction, outstanding at 30 Sep 2026, rate, repayment, security; TL-II monthly schedule with formulas |
| 15 | `02_Financial/07_KPI_Certificate.pdf` | digital PDF | 2–3 | auditor's certificate on 16 KPIs for 4 periods (Audit Committee approval 25 Oct 2026) |
| 16 | `02_Financial/08_Working_Capital_Certificate.pdf` | digital PDF | 2–3 | actual FY24–FY26 and estimated FY27E–FY28E with holding levels, funding pattern, justifications |
| 17 | `02_Financial/09_Funds_Deployed_Certificate.pdf` | digital PDF | 1–2 | ₹186.00 lakhs deployed till 15 Oct 2026 from internal accruals (advance to Ravira Machines) |
| 18 | `02_Financial/10_Statement_of_Special_Tax_Benefits.pdf` | digital PDF | 2–3 | s.115BAA, s.80JJAA (not availed), EPCG, RoDTEP; nothing for shareholders |
| 19 | `02_Financial/11_Sanction_Letter_Kalindi_Bank.pdf` | digital PDF | 3–4 | fictitious bank letterhead; CC renewal 2,200, LC 200, BG 75, TL-I/TL-II continued; margins, security, covenants (TOL/TNW ≤ 2.00x, CR ≥ 1.25x, DSCR ≥ 1.40x); **negative covenant: no change in shareholding / public issue without bank consent**; prepayment from equity allowed; annexure with TL-II original terms |
| 20 | `03_Business/01_Company_Profile_Business_Note.docx` | Word | 18–25 | management's business information note: overview, history table, products (5), process (8 steps), machinery, capacity table, utilities, certifications, customers (anonymised A–J) and concentration, states, exports, order book, sales organisation, raw materials and related-party supplier, competition, strengths, weaknesses (incl. single plant, concentration, fire NOC expired), strategy, HR, IT, EHS and CSR, properties, items not yet available |
| 21 | `03_Business/02_Operational_Data.xlsx` | xlsx | – | capacity and utilisation (formulas), product mix, end-use, states (shares + ₹ by formula), customers/suppliers, employees, machinery, order book |
| 22 | `03_Business/03_Process_Flow_Chart.png` | image (clean diagram) | 1 | matplotlib boxes-and-arrows flow: granules → blown film; film → printing → lamination → curing → slitting → (pouch making) → QC → dispatch; cylinders/pre-press side branch |
| 23 | `03_Business/04_Industry_Report_Arthaveda.pdf` | digital PDF | 35–50 | see section 6 |
| 24 | `03_Business/05_Insurance_and_IP_Register.xlsx` | xlsx | – | 7 policies (D&O not taken), 4 IP items (one trademark objected) |
| 25 | `03_Business/06_Plant_Photographs_Captioned.pdf` | digital PDF | 4–6 | matplotlib-drawn schematic "photo plates" (no real photos): plant layout plan with areas, machine hall schematic, captions; marked "illustrative schematic" |
| 26 | `04_People/01_Promoter_Director_KMP_Profiles.docx` | Word | 8–12 | promoter profile tables and bios, promoter group list (with one item "to be confirmed"), confirmations, board table, other director bios, relationships, committees, remuneration, shareholding, borrowing powers, KMP/SMP table and remuneration, changes in KMP |
| 27 | `04_People/02_Director_Consents_and_Declarations.pdf` | scanned PDF | 6 | one page per director: consent to act, declaration of non-disqualification (s.164), DIN, signature "Sd/-" |
| 28 | `05_Legal_and_Approvals/01_Litigation_Certificate_Legal_Counsel.docx` | Word | 5–8 | per ICDR categories for company / promoters / directors / group companies; materiality threshold computation; creditors table (MSME, material, others) at 30 Sep 2026; confirmations |
| 29 | `05_Legal_and_Approvals/02_Licences_and_Approvals.xlsx` | xlsx | – | 17 approvals with numbers, dates, validity, status (fire NOC expired, renewal pending; LEI not obtained) |
| 30 | `05_Legal_and_Approvals/03_Factory_Licence.jpg` | image (photo-style) | 1 | factory licence, valid to 31 Dec 2026 |
| 31 | `05_Legal_and_Approvals/04_GPCB_Consent_CCA.jpg` | image (scan-style) | 1 | CC&A, valid to 15 Mar 2027 |
| 32 | `05_Legal_and_Approvals/05_Fire_NOC_Expired.jpg` | image (scan-style) | 1 | valid to 20 Sep 2026 (expired) |
| 33 | `05_Legal_and_Approvals/06_GST_Registration_Certificate.pdf` | digital PDF | 2–3 | "format illustration", legal name updated 18 Jul 2026, additional places of business |
| 34 | `05_Legal_and_Approvals/07_Leave_and_Licence_Warehouse.pdf` | scanned PDF | 4–6 | 11-month leave and licence with Kavita Desai (related party), ₹1,25,000/month, deposit ₹5,00,000 |
| 35 | `05_Legal_and_Approvals/08_Group_Companies_and_RPT.xlsx` | xlsx | – | Desai Polymers LLP, Ashtavira Packaging Solutions Pvt Ltd (dormant, negative net worth FY26); RPT by period |
| 36 | `06_Offer/01_Note_on_Proposed_Issue.docx` | Word | 5–7 | issue structure (all price items `[●]`), objects with deployment, funds deployed, debt prepayment and pending bank NOC, intermediaries, timeline, open items for BRLM |
| 37 | `06_Offer/02_Objects_Project_Cost.xlsx` | xlsx | – | summary with formulas, quotation-wise plant and machinery, solar breakdown |
| 38 | `06_Offer/03_Machinery_Quotations.pdf` | scanned PDF | 4–6 | three supplier quotations (Ravira Machines: press + slitter; Sumedh Converting: 2 pouch machines; Optiscan Vision GmbH: inspection system in EUR) |
| 39 | `06_Offer/04_Solar_EPC_Quotation.pdf` | digital PDF | 2–3 | Suryamitra Renewables, 1.20 MWp, ₹520.00 lakhs, items, generation 1,752 MWh, payback ~3.5 years |
| 40 | `06_Offer/05_Selling_Shareholder_Consent.docx` | Word | 1–2 | Hemant Desai, up to 4,00,000 shares |
| 41 | `06_Offer/06_Chartered_Engineer_Capacity_Certificate.pdf` | scanned PDF | 2 | Er. Bhavin S. Mehta, 19 Oct 2026: installed capacity, production, utilisation, basis of computation (3 shifts × 300 days, 180 m/min, 72 g/m², 1,000 mm web) |

Realism details to include across files (they are what make it "issuer grade"):
- Letterheads per sender (company, auditor, bank, law firm, suppliers), dated, addressed, signed "Sd/-" with
  designation; UDINs on auditor documents; reference numbers; "Certified true copy" endorsements.
- Different authors produce different styles: auditor PDFs (Arial, dense tables), legal (Times), management notes
  (Word, Arial), Excel registers. Minor inconsistencies real bundles have are fine if they do not change facts
  (e.g. "H1 FY27" vs "six months ended 30 September 2026").
- Scanned documents are the older or signed ones (MoA, audited FY24/FY25, allotment records, lease, quotations,
  consents, CE certificate); recent drafts are digital.
- Real bundles have open items; include these (consistently, never contradicting each other): fire NOC expired,
  GPCB show-cause pending, LEI missing, market maker not appointed, bank NOC for the Issue awaited, name change not yet
  intimated to GIDC, one promoter-group relative's entity "to be confirmed".

## 6. Industry report (`04_Industry_Report_Arthaveda.pdf`, 35–50 pages)

Fictitious research firm "Arthaveda Research & Advisory Private Limited", dated 20 October 2026, commissioned by the
Company for the IPO. Sections: disclaimer and methodology; macro backdrop (India GDP, consumption, inflation,
urbanisation; **all figures labelled "illustrative synthetic data"**, do not present invented numbers as official
statistics); global packaging; Indian packaging industry by type; Indian flexible packaging market size FY2020–FY2026
and forecast FY2027–FY2031 (₹ crore, CAGR tables); segmentation by material (BOPP, PET, PE, foil, paper), by format
(roll stock, pouches, sachets, sleeves), by end-use (snacks, staples, dairy, personal care, agro, pharma), by region
(West, North, South, East; Gujarat and Maharashtra detail); demand drivers; challenges (polymer price volatility,
EPR and plastic waste rules described only in general terms, recyclability, fragmentation); technology trends
(solventless lamination, mono-material laminates, inline inspection, solar adoption in converting plants);
competitive landscape with **6–8 fictitious peers** (names invented, e.g. "Sarvottam Packaging Limited"), peer table
(revenue, EBITDA margin, RoNW, capacity) where the issuer sits mid-pack; issuer positioning; SWOT; outlook. Include
12–18 matplotlib charts (line, bar, stacked bar, pie) and 15–25 tables. Numbers must be internally consistent
(segment shares sum to 100%, CAGRs match the size tables) and the issuer's figures must match the master data.

## 7. Checks you must run (and fix until clean)

1. Model: balance sheet balances (|assets − liabilities| < 0.01) and cash flow net change = Δcash for every period;
   restated vs audited PAT difference equals the adjustment; working-capital funding positive.
2. Cross-document: extract text from every digital PDF (PyMuPDF), Word (python-docx) and Excel (openpyxl
   `data_only=True`) file and assert a list of anchor values appears where expected, e.g. FY26 revenue `12,688.75`,
   FY26 PAT `774.18`, pre-issue shares `1,00,00,000`, fresh issue `36,00,000`, objects total `4,230.00`, funds deployed
   `186.00`, GST demand `18.62`, materiality threshold `29.86`, TL-II outstanding `468.00`.
3. Excel: every formula cell has a cached value (no `None` on `data_only=True` reads); no `#REF!`/`#DIV/0!`.
4. PDFs: page counts within the targets in section 5; scanned PDFs have no text layer (PyMuPDF `get_text()` empty) and
   digital ones do.
5. Visual QA: rasterise page 1 and one table-heavy page of every PDF and every image at 100 dpi into
   `out/_qa/` and look at them (Read the images). Check: no text overflow out of table cells, no clipped columns,
   watermark visible but light, ₹ renders (no boxes), letterheads correct, scans look like scans.
6. Totals: file count, total pages, total size within section 5 targets; print a summary table.
7. A small offline `check_bundle.py` that re-runs checks 1–4 and 6 in one command.

## 8. Order of work (checkpoints)

1. If `sme_drhp_drafter/bundles/` exists, read its `*.py` files first.
2. Master data and model (`issuer.py`): run, compare with the reference values in section 4.
3. Financial PDFs → render → visual QA → fix layout. Then legal PDFs, Word, Excel, industry report, schematics.
4. Scan simulation and images; then `build_bundle.py` (index workbook last).
5. Run all checks (section 7) and fix until clean.
6. Final report: a table of every file (format, pages, KB, scanned or digital), totals, check results, and anything
   you could not meet (say so plainly).

---

## Appendix A — master data (use exactly)

### A.1 Company

| field | value |
|---|---|
| name / former name | Ashtavira Flexipak Limited / Ashtavira Flexipak Private Limited |
| CIN / former CIN | U22220GJ2012PLC071846 / U22220GJ2012PTC071846 |
| incorporated | 14 August 2012, RoC Gujarat at Ahmedabad; conversion EGM 10 June 2026; fresh COI 2 July 2026 |
| registered office and factory | Plot No. 214-216, GIDC Industrial Estate, Sanand-II, Ahmedabad - 382 110, Gujarat |
| warehouse | Shed No. 7, Shree Hari Logistics Park, Changodar, Ahmedabad - 382 213 (licensed from Kavita Desai) |
| corporate office | Office No. 902, Iscon Elegance, S.G. Highway, Prahlad Nagar, Ahmedabad - 380 015 (unrelated licensor, ₹0.30 lakhs/month, 36 months from 1 May 2024) |
| contacts | +91 79 4890 2214; investors@ashtavira-synthetic.example; www.ashtavira-synthetic.example |
| GSTIN / PAN / IEC / Udyam | 24AAKCA4718M1Z6 / AAKCA4718M / 0812018734 / UDYAM-GJ-01-0047218 (medium) |
| NIC | 22220 |
| plant | land 14,850 sq m (99-year GIDC lease from 12 Dec 2012), built-up 9,420 sq m; HT load 1,650 kVA; DG 1,250 kVA; PNG thermic fluid heater; ZLD |
| LEI | not obtained |

### A.2 People

Promoters: **Hemant Ramniklal Desai** (54, DOB 17 Feb 1972, DIN 02718465, Chairman and MD, B.E. Chemical Gujarat
University 1994, 30 years, Selling Shareholder, designated partner Desai Polymers LLP, director Ashtavira Packaging
Solutions Pvt Ltd, PAN XXXXX4471X); **Kavita Hemant Desai** (50, DOB 3 Sep 1976, DIN 02718472, WTD, B.Com 1996,
24 years, PAN XXXXX9132X). Address both: Bungalow No. 12, Shivalik Greens, Bodakdev, Ahmedabad - 380 054.

Other directors: Parth Hemant Desai (27, DIN 09841276, WTD, promoter group, B.Tech Printing & Packaging + MBA,
director from 1 Apr 2023); Mahesh Chandrakant Trivedi (61, DIN 06614390, ID, CA, chairs Audit Committee); Dr. Ananya
Srinivas Rao (47, DIN 08260517, ID, Ph.D. Polymer Science, chairs NRC); Vikram Harish Sethi (58, DIN 07390824, ID,
B.E. + PGDM, chairs SRC). IDs appointed 15 Jul 2026 for five years; executives re-designated 15 Jul 2026 for five
years. Committees constituted 20 Jul 2026 (Audit, NRC, SRC, CSR) + IPO Committee 28 Aug 2026.

KMP / SMP: Sanjay Prakash Khatri (CFO, 44, CA, joined 1 Jun 2019, holds 75,000 shares); Nidhi Rajesh Purohit (CS &
Compliance Officer, 31, ICSI A58214, joined 15 Jul 2026); Rakesh Govind Joshi (Plant Head, 49, joined 3 Jan 2014,
holds 75,000 shares); Amit Kumar Varma (Head Sales & Marketing, 42, joined 10 Aug 2018); Dr. Meera Krishnan Iyer
(Head QA, 39, joined 1 Feb 2021).

Remuneration ₹ lakhs (FY23 / FY24 / FY25 / FY26 / H1): Hemant 42.00/48.00/54.00/60.00/36.00; Kavita
24.00/30.00/33.00/36.00/21.00; Parth 0/18.00/20.40/24.00/15.00; Khatri 21.60/23.40/25.80/28.20/15.60; Purohit H1 2.95.
SMP FY24/FY25/FY26/H1: Joshi 14.90/16.10/17.40/9.30; Varma 16.20/17.60/19.20/10.20; Iyer 12.60/13.80/15.00/8.10.
New terms from 15 Jul 2026: ₹6.00 / 3.50 / 2.50 lakhs per month; ID sitting fees ₹20,000 per Board meeting.

Promoter group: Parth Hemant Desai; Hemant Ramniklal Desai HUF; Ramniklal Chhaganlal Desai (father, 81); Sarlaben
Ramniklal Desai (mother); Nirav Ramniklal Desai (brother) and Dipika Nirav Desai; Bharatkumar Jayantilal Shah and
Hansaben Bharatkumar Shah (Kavita's parents); Rupal Ketan Parikh (sister); Desai Polymers LLP; Ashtavira Packaging
Solutions Pvt Ltd. Open item: father's 15% interest in M/s R. C. Desai & Sons "to be confirmed".

Advisers: BRLM Meridian Capital Advisors Pvt Ltd (INM000013472, 1201 Shapath-V, S.G. Highway, Ahmedabad); Registrar
Lakshya Registry Services Pvt Ltd (INR000004918); legal counsel Kanoria Sharma & Partners (Adv. Ritika Kanoria);
statutory auditor N K Bhatt & Co., FRN 118742W, partner CA Nirav K. Bhatt, M. No. 112684, peer review cert 016271
valid till 31 Jan 2029, appointed AGM 30 Sep 2022 for FY23–FY27 (previous auditor R J Kothari & Associates, FRN
131904W); industry research Arthaveda Research & Advisory Pvt Ltd; banker Kalindi Bank Limited, Navrangpura branch;
market maker not appointed; CE Er. Bhavin S. Mehta.

### A.3 Share capital

Allotments (all ₹10 FV): 14 Aug 2012 subscription at ₹10 — Hemant 5,000, Kavita 5,000; 31 Mar 2014 rights at ₹10 —
Hemant 2,95,000, Kavita 1,95,000; 15 Feb 2017 preferential at ₹40 — Hemant 2,20,000, Kavita 1,50,000, Parth 1,00,000,
HUF 30,000; 28 Mar 2020 conversion of unsecured loans at ₹55 — Hemant 6,00,000, Kavita 2,50,000, Parth 60,000,
HUF 30,000, Jignesh Natvarlal Shah 15,000, Pooja Dinesh Mehta 15,000, Rakesh Govind Joshi 15,000, Sanjay Prakash
Khatri 15,000; 5 Aug 2026 bonus 4:1 (80,00,000 shares). Pre-bonus 20,00,000; **pre-issue 1,00,00,000**: Hemant
56.00%, Kavita 30.00%, Parth 8.00%, HUF 3.00%, four others 0.75% each. Securities premium ₹600 lakhs (₹150 + ₹450).
Authorised capital: ₹5 lakh (2012), ₹50 lakh (20 Mar 2014), ₹1 crore (10 Feb 2017), ₹2.5 crore (20 Mar 2020),
₹15 crore (1 Aug 2026).

### A.4 Offer and objects

Fresh issue up to 36,00,000; OFS up to 4,00,000 by Hemant Desai; total up to 40,00,000; BSE SME; book-built; price,
lot, market maker `[●]`. Board 28 Aug 2026; EGM 25 Sep 2026; SS consent 3 Oct 2026. Objects (₹ lakhs, FY27 / FY28):
plant and machinery 1,860.00 (1,244.00 / 616.00); 1.20 MWp rooftop solar 520.00 (0 / 520.00); prepayment of TL-II
400.00 (400.00 / 0); working capital 1,450.00 (0 / 1,450.00); total 4,230.00; GCP and issue expenses `[●]`. Funds
deployed ₹186.00 lakhs to 15 Oct 2026 (internal accruals; advance to Ravira, quotation RMPL/Q/2026/0912).

Quotations: Ravira Machines Pvt Ltd, Vadodara — 10-colour ELS rotogravure press 1,300 mm 300 m/min ₹1,145.00 (RMPL/Q/2026/0912,
12 Sep 2026, valid 11 Mar 2027, 26 weeks) and duplex slitter-rewinder ₹148.50 (RMPL/Q/2026/0913); Sumedh Converting
Systems Pvt Ltd, Vasai — 2 pouch machines × ₹186.00 = ₹372.00 (SCS/26-27/Q-0417, 18 Sep 2026, valid 17 Dec 2026);
Optiscan Vision GmbH, Germany — inline inspection EUR 2,10,000 at ₹92.62/EUR incl. duty and freight = ₹194.50
(OSV-IN-26-0388, 24 Sep 2026). Solar: Suryamitra Renewables Pvt Ltd, Gandhinagar, SRPL/EPC/2026/221, 30 Sep 2026 —
modules 268.40, inverters 61.20, structure 72.80, cabling 48.60, net-metering 31.50, installation/O&M 37.50 = 520.00.

### A.5 Financial drivers (FY23 / FY24 / FY25 / FY26 / H1FY27)

| driver | values |
|---|---|
| revenue from operations | 8,012.60 / 9,240.50 / 10,815.30 / 12,688.75 / 7,105.40 |
| scrap sales | 131.20 / 152.40 / 171.85 / 196.30 / 108.65 |
| export incentives | 3.90 / 4.85 / 6.20 / 8.15 / 4.70 |
| export share of sale of products % | (FY23 6.9) 7.21 / 8.12 / 9.04 / 9.37 |
| materials % of revenue | 70.20 / 69.90 / 69.20 / 68.70 / 68.40 |
| employee % | 5.70 / 5.60 / 5.50 / 5.40 / 5.50 |
| other expenses % | 13.55 / 13.40 / 13.10 / 12.90 / 12.70 |
| other income | 31.80 / 38.20 / 45.60 / 52.10 / 31.40 (FD interest at 6.75% on avg lien FDs; forex gain 0.38% of exports; 1.10 × FRAC interest on deposits; misc balances) |
| RM days / FG+WIP days | 39,14 / 38,14 / 37,14 / 36,13 / 36,13 |
| debtor days / creditor days | 82,55 / 84,53 / 85,50 / 83,48 / 84,48 |
| bank charges | 16.40 / 18.00 / 24.50 / 21.00 / 11.80 |
| auditor fees | 5.00 / 5.50 / 6.00 / 7.25 / 4.00 |
| gratuity paid | 3.10 / 4.00 / 4.60 / 5.10 / 2.80 |
| historical net profit for CSR | FY20 290.00, FY21 352.00, FY22 418.00 |

Balance-sheet inputs (Mar22 / Mar23 / Mar24 / Mar25 / Mar26 / Sep26):

| item | values |
|---|---|
| stores and spares | 74.00 / 80.00 / 85.00 / 92.00 / 104.00 / 110.00 |
| security deposits | 44.00 / 46.00 / 48.00 / 51.50 / 51.50 / 53.00 |
| CWIP | 0 / 0 / 0 / 35.00 / 145.00 / 210.00 |
| capital advances | 0 / 0 / 0 / 0 / 60.00 / 186.00 |
| gratuity provision (90% non-current) | 42.00 / 52.00 / 76.60 / 92.80 / 110.40 / 121.90 |
| income-tax liability (net) | 12.80 / 15.20 / 18.40 / 22.60 / 27.90 / 41.30 |
| margin-money FDs (lien) | 75.00 / 80.00 / 80.00 / 85.00 / 90.00 / 90.00 |
| cash on hand | 5.10 / 6.40 / 4.85 / 7.20 / 5.65 / 6.10 |
| TL-I (Kalindi, sanctioned 600, 18 Jun 2021) | 600 / 480 / 360 / 240 / 120 / 60 (current maturity 120, Sep26 60) |
| TL-II (Kalindi, sanctioned 750 on 26 Jun 2024, 720 disbursed, ₹12/month from Jan 2025) | 0 / 0 / 0 / 684 / 540 / 468 (current maturity 144 from Mar25) |
| vehicle loans (Vasundhara Finserv, NBFC) | 68.00 / 52.00 / 71.40 / 47.80 / 44.60 / 36.20 (current 22.40 / 19.60 / 24.80 / 21.20 / 17.90 / 16.40) |
| cash credit (Kalindi; limit 1,800 → 2,200 from 14 Aug 2025) | 1,105 / 1,240 / 1,320 / 1,325 / 1,560 / 1,705 |
| unsecured loan from Hemant Desai (9% p.a.) | 120 / 150 / 180 / 210 / 160 / 140 |
| opening (Mar22) RM / WIP / FG / receivables / payables / OCA / OCL / DTL | 540 / 110 / 170 / 1,520 / 985 / 228 / 182 / 150.00 |

Rates: TL 9.25%, CC 9.60%, vehicles 9.80%, unsecured 9.00%. Non-fund: BG 45.00, LC 120.00 (118.40 used at Sep26).

PPE at 31 Mar 2022 (gross / accumulated): leasehold land 210.00/16.78 (1.01%); buildings 1,180.00/222.60 (3.17%);
plant and machinery 3,340.00/1,075.00 (6.33%); electrical 310.00/144.00 (10%); furniture 34.00/28.00 (9.5%); vehicles
118.00/38.00 (11.88%); computers 26.00/22.00 (31.67%). Additions: FY23 P&M 300, furniture 30, computers 20; FY24 P&M
360, computers 18, vehicles 42; FY25 P&M 820, buildings 120, electrical 40; FY26 P&M 480, buildings 60, furniture 20,
computers 25, vehicles 25; H1 P&M 190, electrical 30, computers 20.

### A.6 Operations (FY24 / FY25 / FY26 / H1FY27)

Lamination capacity MT 8,400 / 9,600 / 9,600 / 4,800; production 5,712 / 7,104 / 7,776 / 3,984. Pouch capacity
(million) 420 / 420 / 540 / 270; production 302 / 319 / 432 / 229. Customers 214 / 238 / 266 / 251. Top-1 %
15.82 / 14.91 / 14.18 / 13.64; top-5 42.11 / 40.63 / 39.84 / 39.12; top-10 58.42 / 59.71 / 61.27 / 60.83; top-10
suppliers 72.40 / 70.86 / 69.52 / 68.81. Product mix %: roll stock 58.1/55.4/52.2/50.3; stand-up & zipper
18.2/19.9/22.1/23.0; centre/3-side seal 13.9/14.1/13.8/13.6; spouted & retort 4.0/4.8/6.0/7.1; sleeves & labels
5.8/5.8/5.9/6.0. End-use %: snacks 31.4/30.2/29.1/28.6; spices, tea, staples 22.6/22.9/23.4/23.8; dairy & frozen
12.8/13.6/14.2/14.5; personal & home care 14.1/14.3/14.6/14.8; agro 12.3/12.1/11.8/11.6; pharma & others
6.8/6.9/6.9/6.7. Domestic states %: Gujarat 41.2/39.8/38.5/37.9; Maharashtra 21.6/22.4/23.1/23.5; MP
11.3/11.6/11.9/12.0; Rajasthan 9.7/9.9/10.2/10.3; others 16.2/16.3/16.3/16.3. Export countries: UAE, Kenya,
Bangladesh, Oman, Tanzania, Nepal. Employees at 30 Sep 2026: production 142, QC/lab 18, maintenance 21, pre-press 9,
stores/purchase/logistics 24, sales 16, finance/secretarial 11, HR/admin 13, contract 58 (total 312). Order book
₹1,842.60 lakhs from 94 customers at 30 Sep 2026. Machines: 8-col press 1,250 mm (2014), 8-col press 1,300 mm (2019),
solvent laminator (2014), solventless laminator (2024), 3-layer blown film (2017), 3 slitters (2014), 7 pouch machines
(2016), 2 spout machines (2022), 2 sleeve machines (2021). Certifications: ISO 9001:2015 and ISO 14001:2015 (Veritrust
Assurance Services, to 14 Mar 2027), FSSC 22000 v6 (Nutrisafe Certification, to 2 Nov 2027), BRCGS Packaging Issue 6
Grade A (to 18 Jan 2027) — certifier names fictitious.

### A.7 Legal, approvals, other registers

Litigation — Company: criminal by company, CC No. 4518/2025, CJM Ahmedabad (Rural), s.138 NI Act vs Shreeji Snacks
and Namkeen, ₹23.86 lakhs, filed 21 May 2025, next hearing 19 Nov 2026; regulatory: GPCB SCN GPCB/AHD-R/2025/1147 dated
11 Mar 2025 (VOC emissions; carbon adsorption unit commissioned 30 Jun 2025; closure awaited); direct tax: s.143(1)(a)
AY 2024-25 ₹6.21 lakhs, rectification filed 9 Jan 2026; indirect tax: s.73 CGST order FY 2021-22 ₹18.62 lakhs +
penalty 1.86, appeal 12 May 2026 with pre-deposit 1.86; civil against (below threshold): Commercial Civil Suit 211/2026,
Precision Inks and Coatings, ₹12.40 lakhs. Promoter Hemant: s.143(1)(a) AY 2023-24 ₹2.14 lakhs. Directors: nil. Group
company Desai Polymers LLP: s.73 SCN FY 2022-23 ₹3.85 lakhs. Creditors at 30 Sep 2026: MSME 47 creditors (22% of trade
payables), material creditors 3 (₹357.35 lakhs combined, each > 5% of payables), others 168 (balance).

Contingent liabilities (Mar24 / Mar25 / Mar26 / Sep26): BG 35.00/35.00/45.00/45.00; LC 64.20/88.50/102.75/118.40; GST
demand 0/0/18.62/18.62; income tax 0/0/6.21/6.21; EPCG export obligation 21.40/46.85/46.85/38.10. Capital commitments
18.00/62.40/148.20/959.00.

Approvals (17 rows): COI 2012; fresh COI 2026; GST (1 Jul 2017); IEC (9 Oct 2012); Udyam (22 Sep 2020); factory licence
AHD/R/25418/2014 valid 31 Dec 2026; CC&A AWH-118274 (16 Mar 2022 – 15 Mar 2027); fire NOC FSC/SND/2023/0816 expired
20 Sep 2026, renewal applied FSC/REN/26/4471; CLRA registration; EPF GJAHD1574192000; ESIC; professional tax; Legal
Metrology packer registration; EPR registration PWP-GJ-ID-24-7731 to 31 Mar 2027; EPCG authorisation 0830017442 (8 Jul
2024, obligation to 7 Jul 2030); HT connection HT-SND-02281; LEI not obtained.

Related parties and transactions (FY23/FY24/FY25/FY26/H1): purchases from Desai Polymers LLP 366.10/412.30/498.75/
560.20/301.15; rent to Kavita 15.00 per year (7.50 in H1); interest on Hemant's loan (model); remuneration (A.2); sitting
fees 1.20 (H1). Balances: payable to Desai Polymers 41.80/48.25/57.10/63.40/70.85 (Mar23…Sep26); remuneration payable
6.20/7.85/8.90/9.95/12.40; rent deposit with Kavita 5.00. Group companies: Desai Polymers LLP (LLPIN AAB-7316, 2 Feb
2016, Vatva; partners Hemant 60%, Parth 40%; turnover/PAT/net worth FY24 1,284.60/21.45/312.80, FY25 1,402.15/24.10/
336.90, FY26 1,538.70/27.85/364.75); Ashtavira Packaging Solutions Pvt Ltd (U74999GJ2019PTC109342, 11 Jul 2019, not
commenced; PAT −0.42/−0.38/−0.35; net worth 0.58/0.20/−0.15; to be struck off after the Offer).

Insurance (Abhayam General Insurance Limited, fictitious): fire & special perils ₹7,850 lakhs to 18 Apr 2027;
burglary 2,400; marine open 1,500; group mediclaim 312; employees' compensation; motor 96.40; D&O not taken.
IP: ASHTAVIRA word mark class 16 no. 5218437 registered (to 17 Nov 2031); logo no. 6012984 objected (reply 22 Aug
2024, hearing awaited); SPOUTPRO no. 6533071 accepted and advertised; domain registered to 2 Mar 2028.

Bank sanction (14 Aug 2025, ref KBL/NVP/MSME/2025-26/0718): margins 25% stock / 40% debtors ≤ 120 days; collateral
EM of factory land and building valued ₹2,840 lakhs (2 Jul 2025); personal guarantees of both promoters; processing
0.30%; covenants as in section 5 row 19.
