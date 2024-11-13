from datetime import datetime

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from airflow.hooks.base import BaseHook

DEFAULT_ARGS = {
    'owner': 'admin',
    'retries': 2,
    'retry_delay': 600,
    'start_date': datetime(2024, 9, 1),
}

API_URL = "https://b2b.itresume.ru/api/statistics"


def load_from_api(**context):
    import requests
    import pendulum
    import psycopg2 as pg

    payload = {
        'client': 'Skillfactory',
        'client_key': 'M2MGWS',
        'start': context['ds'],
        'end': pendulum.parse(context['ds']).add(days=1).to_date_string(),

    }
    response = requests.get(API_URL, params=payload)
    data = response.json()

    connection = BaseHook.get_connection('conn_pg')

    with pg.connect(
        dbname='etl',
        sslmode='disable',
        user=connection.login,
        password=connection.password,
        host=connection.host,
        port=connection.port,
        connect_timeout=600,
        keepalives_idle=600,
        tcp_user_timeout=600
    ) as conn:
        cursor = conn.cursor()

        for el in data:
            row = []
            passback_params = dict(el['passback_params'])
            row.append(el['lti_user_id'])
            row.append(el['is_correct'])
            row.append(el['attempt_type'])
            row.append(el['created_at'])
            row.append(passback_params['oauth_consumer_key'])
            row.append(passback_params['lis_result_sourcedid'])
            row.append(passback_params['lis_outcome_service_url'])

            cursor.execute("INSERT INTO admin_table VALUES ($1, $2, $3, $4, $5, $6, $7)", row)

        conn.commit()


with DAG(
    dag_id="load_from_api_to_pg",
    tags=['utils', 'admin'],
    schedule='@daily',
    default_args=DEFAULT_ARGS,
    max_active_runs=1,
    max_active_tasks=1
) as dag:

    dag_start = EmptyOperator(task_id='dag_start')
    dag_end = EmptyOperator(task_id='dag_end')

    load_from_api = PythonOperator(
        task_id='load_from_api',
        python_callable=load_from_api,
    )

    dag_start >> load_from_api >> dag_end
