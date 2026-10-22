from pathlib import Path
from datetime import datetime
import json
import random
import numpy as np
import pandas as pd
from faker import Faker

# Install: pip install pandas numpy Faker
ROWS_PER_TABLE = 1_000_000
CHUNK_SIZE = 100_000
OUTPUT_DIR = Path('fintech360_bronze')
SEED = 42

fake = Faker('en_IN')
Faker.seed(SEED)
random.seed(SEED)
np.random.seed(SEED)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
START = pd.Timestamp('2022-01-01')
END = pd.Timestamp('2026-10-01')
SPAN_SECONDS = int((END - START).total_seconds())

LOAN_STATUSES = ['APPLIED', 'APPROVED', 'DISBURSED', 'CLOSED', 'REJECTED', 'DEFAULTED']
EMI_STATUSES = ['PAID', 'PENDING', 'OVERDUE', 'PARTIAL', 'BOUNCED']
UPI_STATUSES = ['SUCCESS', 'FAILED', 'PENDING', 'REVERSED']
CATEGORIES = ['SALARY', 'RENT', 'GROCERIES', 'UTILITIES', 'FOOD', 'TRAVEL', 'SHOPPING', 'MEDICAL', 'EMI_PAYMENT', 'TRANSFER', 'CASH_WITHDRAWAL', 'OTHER']


def to_epoch_seconds(values):
    """Convert pandas-compatible timestamps to Unix epoch seconds (UTC)."""
    ts = pd.to_datetime(values, utc=True, errors='coerce')
    return (ts.astype('int64') // 1_000_000_000).where(ts.notna(), np.nan).astype('Int64')

def add_audit_and_json(df, base_timestamps, json_column, payload_builder):
    """Add created_at/updated_at Unix epoch seconds and a JSON-string payload."""
    base = pd.to_datetime(base_timestamps, errors='coerce')
    # Use base event time as created_at; updated_at is created_at plus 0-30 days.
    update_offsets = np.random.randint(0, 30 * 24 * 60 * 60 + 1, len(df))
    updated = base + pd.to_timedelta(update_offsets, unit='s')
    df['created_at'] = to_epoch_seconds(base)
    df['updated_at'] = to_epoch_seconds(updated)
    df[json_column] = [json.dumps(payload_builder(i), separators=(',', ':'), ensure_ascii=False) for i in range(len(df))]
    return df


def timestamps(n):
    seconds = np.random.randint(0, SPAN_SECONDS + 1, size=n)
    return START + pd.to_timedelta(seconds, unit='s')


def add_quality_issues(df, fields):
    # Intentionally inject ~0.2% bad records for Silver-layer validation demos.
    n = len(df)
    if n < 500:
        return df
    bad = np.random.choice(n, max(1, int(n * 0.002)), replace=False)
    for idx, (column, value) in enumerate(fields):
        subset = bad[idx::len(fields)]
        if len(subset):
            df.loc[subset, column] = value
    return df


def generate_loans(n, start_id):
    ids = np.arange(start_id + 1, start_id + n + 1)
    app_ts = timestamps(n)
    status = np.random.choice(LOAN_STATUSES, n, p=[.20, .12, .42, .12, .10, .04])
    principal = np.clip(np.random.lognormal(9.4, .65, n), 2000, 500000).round(2)
    tenure = np.random.choice([3, 6, 9, 12, 18, 24, 36], n, p=[.08, .20, .08, .36, .08, .16, .04])
    disbursed = app_ts + pd.to_timedelta(np.random.randint(0, 15, n), unit='D')
    disbursed = pd.Series(disbursed).where(np.isin(status, ['DISBURSED', 'CLOSED', 'DEFAULTED']), pd.NaT)
    df = pd.DataFrame({
        'loan_id': ids,
        'customer_id': np.random.randint(1, 500001, n),
        'application_id': [f'APP{x:09d}' for x in ids],
        'loan_source': np.random.choice(['APP', 'WEB', 'PARTNER', 'REFERRAL', 'AGENT'], n),
        'loan_purpose': np.random.choice(['PERSONAL', 'MEDICAL', 'EDUCATION', 'TRAVEL', 'HOME_REPAIR', 'OTHER'], n),
        'principal_amount': principal,
        'annual_interest_rate_pct': np.round(np.random.uniform(12, 48, n), 2),
        'tenure_months': tenure,
        'loan_status': status,
        'application_ts': app_ts,
        'disbursement_ts': disbursed,
        'maturity_date': disbursed + pd.to_timedelta(tenure * 30, unit='D'),
        'currency': 'INR',
        'source_system': 'SYNTHETIC_LOAN_APP'
    })
    df = add_audit_and_json(
        df, app_ts, 'loan_details_json',
        lambda i: {
            'application_channel': str(df['loan_source'].iloc[i]),
            'employment_type': random.choice(['SALARIED', 'SELF_EMPLOYED', 'CONTRACT']),
            'income_monthly_estimate': round(float(np.random.lognormal(10.2, 0.45)), 2),
            'kyc_status': random.choice(['VERIFIED', 'PENDING', 'FAILED']),
            'risk_flags': random.sample(['THIN_FILE', 'HIGH_UTILIZATION', 'RECENT_ENQUIRIES', 'NO_FLAGS'], k=1)
        })
    return add_quality_issues(df, [('customer_id', np.nan), ('principal_amount', -1), ('loan_status', 'UNKNOWN_STATUS')])


def generate_emi(n, start_id):
    ids = np.arange(start_id + 1, start_id + n + 1)
    due = pd.Series(timestamps(n)).dt.normalize() + pd.to_timedelta(np.random.choice([0, 5, 10, 15, 20, 25], n), unit='D')
    amount = np.clip(np.random.lognormal(7.5, .45, n), 300, 100000).round(2)
    status = np.random.choice(EMI_STATUSES, n, p=[.56, .20, .12, .07, .05])
    paid = np.where(status == 'PAID', amount, np.where(status == 'PARTIAL', (amount * np.random.uniform(.1, .8, n)).round(2), 0))
    paid_at = pd.Series(pd.NaT, index=np.arange(n), dtype='datetime64[ns]')
    mask = np.isin(status, ['PAID', 'PARTIAL'])
    paid_at.loc[mask] = due.loc[mask] + pd.to_timedelta(np.random.randint(-5, 20, mask.sum()), unit='D')
    dpd = np.where(np.isin(status, ['OVERDUE', 'BOUNCED']), np.random.randint(1, 181, n), 0)
    df = pd.DataFrame({
        'emi_id': ids,
        'loan_id': np.random.randint(1, ROWS_PER_TABLE + 1, n),
        'installment_number': np.random.randint(1, 37, n),
        'due_date': due,
        'emi_amount': amount,
        'paid_amount': paid,
        'paid_at': paid_at,
        'emi_status': status,
        'days_past_due': dpd,
        'payment_method': np.random.choice(['UPI', 'NACH', 'BANK_TRANSFER', 'CARD', 'CASH'], n),
        'late_fee_amount': np.where(dpd > 0, np.minimum(dpd * np.random.uniform(2, 10, n), 5000).round(2), 0),
        'schedule_created_ts': due - pd.to_timedelta(np.random.randint(10, 45, n), unit='D')
    })
    df = add_audit_and_json(
        df, df['schedule_created_ts'], 'emi_details_json',
        lambda i: {
            'mandate_type': random.choice(['NACH', 'UPI_AUTOPAY', 'CARD_AUTOPAY']),
            'bounce_count_lifetime': int(np.random.poisson(0.25)),
            'reminder_sent': bool(random.choice([True, False])),
            'payment_attempts': int(random.randint(0, 4))
        })
    df = df.drop(columns=['schedule_created_ts'])
    return add_quality_issues(df, [('emi_amount', -10), ('emi_status', 'INVALID_STATUS')])


def generate_upi(n, start_id):
    ids = np.arange(start_id + 1, start_id + n + 1)
    payer = np.random.randint(1, 500001, n)
    payee = np.random.randint(500001, 700001, n)
    txn_ts = timestamps(n)
    df = pd.DataFrame({
        'upi_txn_id': [f'UPI{x:010d}' for x in ids],
        'customer_id': payer,
        'payer_vpa': [f'user{x}@syntheticupi' for x in payer],
        'payee_vpa': [f'merchant{x}@syntheticupi' for x in payee],
        'merchant_category': np.random.choice(['GROCERY', 'FOOD', 'TRAVEL', 'UTILITIES', 'SHOPPING', 'EDUCATION', 'HEALTHCARE', 'ENTERTAINMENT', 'PERSONAL_TRANSFER', 'OTHER'], n),
        'transaction_amount': np.clip(np.random.lognormal(5.2, 1.2, n), 1, 200000).round(2),
        'currency': 'INR',
        'transaction_ts': txn_ts,
        'transaction_status': np.random.choice(UPI_STATUSES, n, p=[.88, .07, .03, .02]),
        'rrn': [f'RRN{random.randint(10**11, 10**12-1)}' for _ in range(n)],
        'upi_app': np.random.choice(['SYNTHETIC_APP_A', 'SYNTHETIC_APP_B', 'SYNTHETIC_APP_C'], n),
        'device_os': np.random.choice(['ANDROID', 'IOS', 'WEB'], n, p=[.78, .17, .05]),
        'is_refund': np.random.choice([False, True], n, p=[.98, .02])
    })
    df = add_audit_and_json(
        df, txn_ts, 'upi_details_json',
        lambda i: {
            'payer_account_type': random.choice(['SAVINGS', 'CURRENT', 'WALLET']),
            'device_risk_score': round(float(np.random.uniform(0, 1)), 3),
            'merchant_vpa_verified': bool(random.choice([True, False])),
            'failure_reason': random.choice([None, None, None, 'INSUFFICIENT_FUNDS', 'BANK_TIMEOUT']) if df['transaction_status'].iloc[i] != 'SUCCESS' else None
        })
    return add_quality_issues(df, [('transaction_amount', -5), ('transaction_status', 'UNKNOWN')])


def generate_bureau(n, start_id):
    ids = np.arange(start_id + 1, start_id + n + 1)
    report_ts = timestamps(n)
    df = pd.DataFrame({
        'bureau_record_id': ids,
        'customer_id': np.random.randint(1, 500001, n),
        'bureau_provider': np.random.choice(['SYNTHETIC_BUREAU_A', 'SYNTHETIC_BUREAU_B', 'SYNTHETIC_BUREAU_C'], n),
        'report_ts': report_ts,
        'credit_score': np.random.normal(710, 70, n).round().clip(300, 900).astype(int),
        'active_accounts': np.random.poisson(2.5, n).clip(0, 30),
        'total_accounts': np.random.poisson(5, n).clip(0, 60),
        'total_outstanding_amount': np.clip(np.random.lognormal(9.5, 1, n), 0, 5000000).round(2),
        'overdue_amount': np.clip(np.random.lognormal(5, 1.2, n), 0, 1000000).round(2),
        'enquiries_last_30d': np.random.poisson(1.2, n).clip(0, 20),
        'enquiries_last_90d': np.random.poisson(2.8, n).clip(0, 40),
        'delinquency_ever': np.random.choice([True, False], n, p=[.22, .78]),
        'written_off_accounts': np.random.poisson(.1, n).clip(0, 10),
        'report_reference': [f'BUR{x:010d}' for x in ids]
    })
    df = add_audit_and_json(
        df, report_ts, 'bureau_details_json',
        lambda i: {
            'score_band': 'HIGH' if int(df['credit_score'].iloc[i]) >= 750 else ('MEDIUM' if int(df['credit_score'].iloc[i]) >= 650 else 'LOW'),
            'secured_accounts': int(np.random.poisson(1.2)),
            'unsecured_accounts': int(np.random.poisson(2.0)),
            'recent_delinquency': bool(random.choice([True, False])),
            'bureau_consent_present': True
        })
    return add_quality_issues(df, [('credit_score', 999), ('customer_id', np.nan)])


def generate_bank(n, start_id):
    ids = np.arange(start_id + 1, start_id + n + 1)
    txn_type = np.random.choice(['CREDIT', 'DEBIT'], n, p=[.38, .62])
    amount = np.clip(np.random.lognormal(7, 1.1, n), 1, 2000000).round(2)
    customer = np.random.randint(1, 500001, n)
    txn_ts = timestamps(n)
    narrations = ['SALARY CREDIT', 'UPI PAYMENT', 'IMPS TRANSFER', 'ATM CASH', 'UTILITY BILL', 'LOAN EMI', 'CARD PAYMENT', 'RENT PAYMENT', 'NEFT CREDIT', 'FOOD DELIVERY', 'GROCERY PURCHASE', 'OTHER']
    df = pd.DataFrame({
        'bank_txn_id': [f'BANK{x:010d}' for x in ids],
        'customer_id': customer,
        'account_id': [f'ACCT{x:09d}' for x in np.random.randint(1, 400001, n)],
        'bank_name': np.random.choice(['SYNTHETIC_BANK_A', 'SYNTHETIC_BANK_B', 'SYNTHETIC_BANK_C', 'SYNTHETIC_BANK_D'], n),
        'transaction_ts': txn_ts,
        'transaction_type': txn_type,
        'transaction_amount': amount,
        'signed_amount': np.where(txn_type == 'CREDIT', amount, -amount),
        'balance_after_txn': np.clip(np.random.lognormal(9.5, .8, n), 0, 10000000).round(2),
        'currency': 'INR',
        'narration': np.random.choice(narrations, n),
        'transaction_category': np.random.choice(CATEGORIES, n),
        'is_salary_like': np.random.choice([True, False], n, p=[.12, .88]),
        'source_file_id': [f'STMT{x:08d}' for x in np.random.randint(1, 250001, n)]
    })
    df = add_audit_and_json(
        df, txn_ts, 'bank_details_json',
        lambda i: {
            'statement_period': random.choice(['2026-01', '2026-02', '2026-03', '2026-04', '2026-05', '2026-06']),
            'channel': random.choice(['MOBILE', 'INTERNET_BANKING', 'ATM', 'BRANCH', 'UPI']),
            'counterparty_type': random.choice(['PERSON', 'MERCHANT', 'EMPLOYER', 'LENDER', 'UTILITY']),
            'is_recurring': bool(random.choice([True, False])),
            'reference_match_status': random.choice(['MATCHED', 'UNMATCHED', 'NOT_APPLICABLE'])
        })
    return add_quality_issues(df, [('transaction_amount', -100), ('customer_id', np.nan)])


def write_csv_chunks(filename, generator):
    path = OUTPUT_DIR / filename
    if path.exists():
        path.unlink()
    first = True
    for offset in range(0, ROWS_PER_TABLE, CHUNK_SIZE):
        n = min(CHUNK_SIZE, ROWS_PER_TABLE - offset)
        df = generator(n, offset)
        df.to_csv(path, index=False, mode='w' if first else 'a', header=first)
        first = False
        print(f'{filename}: {offset + n:,}/{ROWS_PER_TABLE:,}')
    print(f'Saved: {path.resolve()}')


if __name__ == '__main__':
    jobs = [
        ('loans.csv', generate_loans),
        ('emi_data.csv', generate_emi),
        ('upi_data.csv', generate_upi),
        ('bureau_data.csv', generate_bureau),
        ('bank_data.csv', generate_bank),
    ]
    print(f'Generating {ROWS_PER_TABLE:,} rows per table ({ROWS_PER_TABLE * len(jobs):,} total rows).')
    for filename, generator in jobs:
        write_csv_chunks(filename, generator)
    print(f'All files created under: {OUTPUT_DIR.resolve()}')
    print('Note: data is synthetic. Check row counts and validate schemas before using in a pipeline.')
