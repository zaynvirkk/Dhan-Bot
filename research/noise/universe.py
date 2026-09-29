"""Disclosure categories added after input audit, before content-variant outcomes."""
EXTRA_CATEGORIES={
 'Credit Rating','Credit Rating- New','Credit Rating- Revision','Credit Rating- Others',
 'Change in Director(s)','News Verification','Cessation',
 'Pendency of Litigation(s)/dispute(s) or the outcome impacting the Company',
 'Monthly Business Updates','Amalgamation/Merger','Action(s) initiated or orders passed',
 'Agreements','Rumour Verification - Regulation 30(11)',
 'Commencement of commercial production/operations','Capacity addition','Scheme of Arrangement',
 'Disclosure of material issue','Other Restructuring','Suspension of Trading','Sale or disposal',
 'Arrangements for strategic, technical, manufacturing, or marketing tie up',
 'Diversification/Disinvestment','Rescission/termination(s)','Awarding of order(s)/contract(s)',
 'Disruption of Operations',
 'Granting/withdrawal/surrender/cancellation/suspension of key licenses/ regulatory approvals',
 'Strikes/Lockouts/Disturbances','Press Release (Revised)',
 'Effect(s) on listed entity due to changed regulatory  framework applicable',
 'Memorandum of Understanding/Agreements','Product launch','Closure of operations',
 'Integrated Filing- Financial',
}

def relevant(record):
    return record['quality']!='OTHER' or record.get('category') in EXTRA_CATEGORIES
