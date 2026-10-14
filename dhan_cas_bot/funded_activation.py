"""Narrow operator-authorised funded subset edit; never touches capital caps."""
import json,re,tomllib
from .config import funded_strategies
from .strategy_inputs import strategy_names


def amend_funded(text,names):
    before=tomllib.loads(text)
    funded_strategies({'funded_strategies':names},strategy_names(before))
    head,sep,tail=text.partition('\n[')
    line='funded_strategies = '+json.dumps(names)
    if 'funded_strategies' in before:
        pattern=r'(?m)^funded_strategies\s*=\s*[^\n]*$'
        if len(re.findall(pattern,head))!=1:raise ValueError('ambiguous funded assignment')
        head=re.sub(pattern,lambda _:line,head)
    else:head=line+'\n'+head
    updated=head+sep+tail;after=tomllib.loads(updated)
    if {k:v for k,v in after.items() if k!='funded_strategies'}!={k:v for k,v in before.items() if k!='funded_strategies'}:
        raise ValueError('unrelated configuration would change')
    return updated
