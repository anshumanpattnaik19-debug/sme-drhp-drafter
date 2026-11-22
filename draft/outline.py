"""SME DRHP section outline (SEBI ICDR Schedule VI order) with the writer of each section (PLAN.md section 3).

writer: inserted | code | template | slm_core | slm_ext
needs:  doc types whose absence is reported as a missing input
checklist: mandatory items per section; a placeholder list until the reviewer fixes it in Week 0
query: words used by the fact router for this section
"""
from __future__ import annotations

WRITERS = {
    "inserted": "Inserted as provided",
    "code": "Code (tables)",
    "template": "Template",
    "slm_core": "SLM · core",
    "slm_ext": "SLM · extended",
}

S = lambda key, title, part, writer, needs=(), checklist=(), query="", subheads=(): {  # noqa: E731
    "key": key, "title": title, "part": part, "writer": writer, "needs": list(needs),
    "checklist": list(checklist), "query": query, "subheads": list(subheads)}

SECTIONS = [
    S("definitions", "Definitions and Abbreviations", "I. General", "template",
      query="company name registered office promoters auditor bank"),
    S("conventions", "Certain Conventions, Presentation of Financial, Industry and Market Data", "I. General", "template",
      query="financial year lakhs restated industry report"),
    S("forward_looking", "Forward-Looking Statements", "I. General", "template"),
    S("summary", "Summary of the Offer Document", "I. General", "slm_ext",
      needs=["business_note", "offer_note", "restated_workings"],
      checklist=["primary business", "industry", "promoters", "offer size", "objects", "pre-issue shareholding",
                 "summary financials", "outstanding litigation", "related party transactions"],
      query="business industry promoter offer objects revenue profit litigation related party"),
    S("risk_factors", "Risk Factors", "II. Risk Factors", "slm_core",
      needs=["litigation", "approvals", "borrowings", "operational_data", "group_rpt"],
      checklist=["internal risks", "external risks", "offer-related risks", "outstanding litigation",
                 "customer concentration", "expired or pending approvals", "indebtedness and covenants",
                 "related party transactions", "contingent liabilities"],
      query="risk litigation customer concentration top customers supplier approval expired fire noc borrowing "
            "covenant related party contingent liabilities negative cash flow capacity utilisation",
      subheads=["Internal Risk Factors", "External Risk Factors", "Risks Relating to the Offer"]),
    S("the_offer", "The Offer", "III. Introduction", "code", needs=["offer_note"],
      query="fresh issue offer for sale equity shares face value market maker reservation"),
    S("summary_financials", "Summary of Financial Information", "III. Introduction", "code",
      needs=["restated_workings"], query="revenue from operations total income profit after tax net worth "
                                           "total assets borrowings ebitda"),
    S("general_info", "General Information", "III. Introduction", "template",
      needs=["coi", "offer_note"], query="registered office cin registrar of companies company secretary "
                                          "compliance officer lead manager registrar to the offer banker auditor"),
    S("capital_structure", "Capital Structure", "III. Introduction", "code",
      needs=["share_capital", "allotment"], query="authorised share capital issued subscribed paid-up allotment "
                                                    "bonus shareholding promoters average cost"),
    S("objects", "Objects of the Offer", "III. Introduction", "slm_core",
      needs=["objects_cost", "quotation", "funds_deployed"],
      checklist=["fund requirement table", "means of finance", "schedule of implementation",
                 "deployment of funds", "details of each object", "quotations relied on",
                 "general corporate purposes", "offer expenses", "monitoring agency or interim use"],
      query="objects project cost machinery quotation solar working capital general corporate purposes "
            "means of finance deployment schedule of implementation offer expenses funds deployed",
      subheads=["Requirement of Funds", "Means of Finance", "Details of the Objects", "Schedule of Implementation",
                "Offer Related Expenses", "Funds Deployed", "Interim Use of Proceeds"]),
    S("basis_price", "Basis for Offer Price", "III. Introduction", "code", needs=["kpi", "restated_workings"],
      query="earnings per share return on net worth net asset value kpi ebitda margin"),
    S("tax_benefits", "Statement of Special Tax Benefits", "III. Introduction", "inserted", needs=["tax_benefits"]),
    S("industry", "Industry Overview", "IV. About the Company", "slm_ext", needs=["industry_report"],
      checklist=["source of industry data", "market size", "growth drivers", "competition", "risks to the industry"],
      query="industry market size growth cagr flexible packaging demand drivers peers competition"),
    S("business", "Our Business", "IV. About the Company", "slm_core",
      needs=["business_note", "operational_data", "insurance_ip"],
      checklist=["overview", "products and services", "manufacturing process", "installed capacity and utilisation",
                 "customers and end-use", "raw materials and suppliers", "competitive strengths", "business strategy",
                 "human resources", "properties", "insurance", "intellectual property"],
      query="business products customers capacity utilisation plant machinery raw material suppliers strengths "
            "strategy employees property insurance trademark export",
      subheads=["Overview", "Our Products", "Manufacturing Process", "Capacity and Capacity Utilisation",
                "Our Customers", "Raw Materials", "Our Competitive Strengths", "Our Business Strategy",
                "Human Resources", "Properties", "Insurance", "Intellectual Property"]),
    S("regulations", "Key Industry Regulations and Policies", "IV. About the Company", "template",
      query="factories act pollution control gst fire safety"),
    S("history", "History and Certain Corporate Matters", "IV. About the Company", "slm_core",
      needs=["coi", "moa", "shareholder_resolution"],
      checklist=["brief history", "change in registered office", "main objects", "amendments to the MoA",
                 "major events and milestones", "holding and subsidiaries", "shareholders' agreements"],
      query="incorporated conversion public company change of name registered office main objects memorandum "
            "amendment milestones subsidiary",
      subheads=["Brief History", "Changes in Registered Office", "Main Objects", "Amendments to the MoA",
                "Key Events and Milestones", "Holding, Subsidiary and Joint Ventures", "Material Agreements"]),
    S("management", "Our Management", "IV. About the Company", "slm_core",
      needs=["people_profiles", "board_resolution", "director_declarations"],
      checklist=["board of directors table", "brief profiles of directors", "remuneration", "shareholding of directors",
                 "corporate governance and committees", "key managerial personnel", "changes in the last three years"],
      query="director managing director whole-time independent din appointed remuneration committee audit "
            "nomination kmp company secretary chief financial officer",
      subheads=["Board of Directors", "Brief Profiles of Our Directors", "Remuneration", "Shareholding of Directors",
                "Corporate Governance", "Committees of the Board", "Key Managerial Personnel", "Changes in the Last Three Years"]),
    S("promoters", "Our Promoters and Promoter Group", "IV. About the Company", "slm_core",
      needs=["people_profiles", "share_capital", "group_rpt"],
      checklist=["details of individual promoters", "change in control", "interest of promoters",
                 "payment or benefit to promoters", "promoter group", "litigation involving promoters"],
      query="promoter promoter group shareholding interest relative benefit change in control experience",
      subheads=["Our Promoters", "Interest of Our Promoters", "Payment or Benefits to Promoters",
                "Change in Control", "Promoter Group"]),
    S("group_companies", "Our Group Companies", "IV. About the Company", "template", needs=["group_rpt"],
      query="group company llp private limited"),
    S("dividend_policy", "Dividend Policy", "IV. About the Company", "template", query="dividend"),
    S("restated_fs", "Restated Financial Information", "V. Financial Information", "inserted", needs=["restated_fs"]),
    S("other_financial", "Other Financial Information", "V. Financial Information", "code", needs=["restated_workings"],
      query="earnings per share return on net worth net asset value ebitda"),
    S("mdna", "Management's Discussion and Analysis of Financial Condition", "V. Financial Information", "slm_ext",
      needs=["restated_workings", "operational_data"],
      checklist=["overview", "significant factors", "results of operations", "comparison of periods", "cash flows",
                 "indebtedness", "contingent liabilities", "related party transactions"],
      query="revenue from operations other income expenses ebitda profit after tax cash flow operating investing "
            "financing borrowings contingent"),
    S("capitalisation", "Capitalisation Statement", "V. Financial Information", "code", needs=["restated_workings"],
      query="total borrowings shareholders funds net worth debt equity"),
    S("indebtedness", "Financial Indebtedness", "V. Financial Information", "code", needs=["borrowings", "sanction_letter"],
      query="term loan cash credit sanctioned outstanding rate of interest repayment security bank"),
    S("litigation", "Outstanding Litigation and Material Developments", "VI. Legal and Other Information", "slm_ext",
      needs=["litigation"],
      checklist=["criminal proceedings", "actions by regulatory authorities", "tax proceedings", "material civil litigation",
                 "materiality policy", "outstanding dues to creditors"],
      query="litigation criminal tax proceedings civil suit materiality creditors msme dues notice"),
    S("approvals", "Government and Other Approvals", "VI. Legal and Other Information", "slm_ext",
      needs=["approvals", "licence"],
      checklist=["incorporation approvals", "tax approvals", "business approvals", "pending approvals", "expired approvals",
                 "intellectual property"],
      query="approval licence registration consent noc valid expired applied renewal factory gst"),
    S("regulatory", "Other Regulatory and Statutory Disclosures", "VI. Legal and Other Information", "template",
      query="authority for the offer board resolution shareholders resolution eligibility"),
    S("terms", "Terms of the Offer", "VII. Offer Information", "template", query="ranking face value"),
    S("offer_structure", "Offer Structure", "VII. Offer Information", "code", needs=["offer_note"],
      query="market maker reservation net offer allocation"),
    S("offer_procedure", "Offer Procedure", "VII. Offer Information", "template"),
    S("foreign_ownership", "Restrictions on Foreign Ownership of Indian Securities", "VII. Offer Information", "template"),
    S("aoa", "Main Provisions of the Articles of Association", "VIII. Articles of Association", "inserted", needs=["aoa"]),
    S("material_contracts", "Material Contracts and Documents for Inspection", "IX. Other Information", "template",
      query="agreement registrar market maker underwriting resolution certificate consent"),
    S("declaration", "Declaration", "IX. Other Information", "template", query="director managing director chief financial officer"),
]

SECTION_BY_KEY = {s["key"]: s for s in SECTIONS}
PARTS = list(dict.fromkeys(s["part"] for s in SECTIONS))
