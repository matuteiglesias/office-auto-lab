"""Read-only publication health for two editorial profiles."""
from __future__ import annotations
import json
import os
from datetime import datetime,timedelta,timezone
from office_runtime.editorial.staging.sheets import GoogleSheetsGateway

def parse(value):
    if not value:return None
    try:
        dt=datetime.fromisoformat(value.replace('Z','+00:00'))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except ValueError:return None

def assess(profile,raw,now,runs=None):
    assert raw and raw[0][:3]==['candidate_id','draft_editable','decision']
    rows=[dict(zip(raw[0],r+['']*(len(raw[0])-len(r)))) for r in raw[1:] if r and r[0]]
    done=[parse(r['updated_at']) for r in rows if r['publisher_status']=='PUBLISHED']
    done=[t for t in done if t]
    last=max(done) if done else None
    upcoming=sorted(t for r in rows if r['decision']=='APPROVE' and not r['publisher_status'] and not r['published_ref'] if (t:=parse(r['scheduled_for'])) and now<=t<=now+timedelta(days=3))
    review=sum(r['decision']=='REVIEW' and not r['published_ref'] for r in rows)
    approved=sum(r['decision']=='APPROVE' and not r['published_ref'] and not r['publisher_status'] for r in rows)
    recent=(runs or [])[-1] if runs and len(runs)>1 else []
    upstream='UPSTREAM_EMPTY' if profile=='dev' and len(recent)>5 and recent[5]=='0' else 'OK'
    if last and now-last<timedelta(hours=30): state='PUBLISHED'
    elif upcoming:state='SCHEDULED'
    elif review:state='AWAITING_APPROVAL'
    elif upstream=='UPSTREAM_EMPTY':state='UPSTREAM_EMPTY'
    else:state='NO_ELIGIBLE_CONTENT'
    alert=not upcoming and (last is None or now-last>timedelta(hours=48))
    return {'profile':profile,'state':state,'upstream':upstream,'alert':alert,'approved':approved,'review':review,'upcoming':len(upcoming),'last_post':last.isoformat() if last else None}

def main():
    now=datetime.now(timezone.utc)
    accounts=[]
    try:
        for profile,env in [('dev','EDITORIAL_DEV_SHEET_ID'),('argentina_econ','EDITORIAL_ARGENTINA_ECON_SHEET_ID')]:
            sid=os.environ.get(env)
            if not sid:raise RuntimeError('missing workbook id')
            gateway=GoogleSheetsGateway.from_environment(spreadsheet_id=sid)
            queue=gateway.read_rows('QUEUE')
            runs=gateway.read_rows('RUNS') if profile=='dev' else None
            accounts.append(assess(profile,queue,now,runs))
    except Exception as exc:
        print(json.dumps({'state':'FAILED','error_class':type(exc).__name__}))
        return 2
    print(json.dumps({'checked_at':now.isoformat(),'accounts':accounts},sort_keys=True))
    summary=os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a') as f:
            f.write('### Editorial X health\n\n')
            f.write('| Account | State | Last post UTC | Approved queue | Review queue | Upcoming 72h | Source |\n|---|---|---|---:|---:|---:|---|\n')
            for r in accounts:
                f.write(f"| {r['profile']} | {r['state']} | {r['last_post'] or '-'} | {r['approved']} | {r['review']} | {r['upcoming']} | {r['upstream']} |\n")
    if any(r['alert'] for r in accounts):
        print('::warning::At least one editorial account has no post in 48 hours and no fresh scheduled content')
        return 1
    return 0

if __name__=='__main__':
    raise SystemExit(main())
