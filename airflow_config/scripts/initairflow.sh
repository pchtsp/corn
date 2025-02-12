#!/usr/bin/env bash
# Airflow 2.0 entrypoint script for baobabsoluciones/docker-airflow based on puckel/docker-airflow https://github.com/puckel/docker-airflow
# User-provided configuration must always be respected.
#
# Therefore, this script must only derives Airflow AIRFLOW__ variables from other variables
# when the user did not provide their own configuration.

# Global defaults and back-compat
: "${AIRFLOW_HOME:="/usr/local/airflow"}"
: "${AIRFLOW__CORE__EXECUTOR:=${EXECUTOR:-Sequential}Executor}"
: "${AIRFLOW__CORE__LOAD_EXAMPLES:="0"}"
: "${AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION:="0"}"
: "${AIRFLOW__API__AUTH_BACKEND:="airflow.api.auth.backend.basic_auth"}"
: "${AIRFLOW__CORE__FERNET_KEY:=${FERNET_KEY:=$(python -c "from cryptography.fernet import Fernet; FERNET_KEY = Fernet.generate_key().decode(); print(FERNET_KEY)")}}"
: "${AIRFLOW_USER:="admin"}"
: "${AIRFLOW_FIRSTNAME:="admin"}"
: "${AIRFLOW_LASTNAME:="admin"}"
: "${AIRFLOW_ROLE:="Admin"}"
: "${AIRFLOW_PWD:="admin"}"
: "${AIRFLOW_USER_EMAIL:="admin@example.com"}"
: "${CORNFLOW_SERVICE_USER:="serviceuser@cornflow.com"}"
: "${CORNFLOW_SERVICE_PWD:="servicecornflow1234"}"

export \
	AIRFLOW_HOME \
	AIRFLOW__CORE__EXECUTOR \
	AIRFLOW__CORE__LOAD_EXAMPLES \
	AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION \
	AIRFLOW__API__AUTH_BACKEND \
	AIRFLOW__CORE__FERNET_KEY \
	AIRFLOW_USER \
	AIRFLOW_FIRSTNAME \
	AIRFLOW_LASTNAME \
	AIRFLOW_ROLE \
	AIRFLOW_PWD \
	AIRFLOW_USER_EMAIL \
  CORNFLOW_SERVICE_USER \
  CORNFLOW_SERVICE_PWD \
  AIRFLOW_LDAP_ENABLE

# Install custom python package if requirements.txt is present
if [ -e "/requirements.txt" ]; then
    $(command -v pip) install --user -r /requirements.txt
fi

# Make SQL connention
  if [ -z "$AIRFLOW__CORE__SQL_ALCHEMY_CONN" ]; then
    # Default values corresponding to the default compose files
    : "${AIRFLOW_DB_HOST:="airflow_db"}"
    : "${AIRFLOW_DB_PORT:="5432"}"
    : "${AIRFLOW_DB_USER:="airflow"}"
    : "${AIRFLOW_DB_PWD:="airflow"}"
    : "${AIRFLOW_DB:="airflow"}"
    : "${AIRFLOW_DB_EXTRAS:-""}"

    AIRFLOW__CORE__SQL_ALCHEMY_CONN="postgresql+psycopg2://${AIRFLOW_DB_USER}:${AIRFLOW_DB_PWD}@${AIRFLOW_DB_HOST}:${AIRFLOW_DB_PORT}/${AIRFLOW_DB}${AIRFLOW_DB_EXTRAS}"
    export AIRFLOW__CORE__SQL_ALCHEMY_CONN

    # Check if the user has provided explicit Airflow configuration for the broker's connection to the database
    if [ "$AIRFLOW__CORE__EXECUTOR" = "CeleryExecutor" ]; then
      AIRFLOW__CELERY__RESULT_BACKEND="db+postgresql://${AIRFLOW_DB_USER}:${AIRFLOW_DB_PWD}@${AIRFLOW_DB_HOST}:${AIRFLOW_DB_PORT}/${AIRFLOW_DB}${AIRFLOW_DB_EXTRAS}"
      export AIRFLOW__CELERY__RESULT_BACKEND
    fi
  else
    if [[ "$AIRFLOW__CORE__EXECUTOR" == "CeleryExecutor" && -z "$AIRFLOW__CELERY__RESULT_BACKEND" ]]; then
      >&2 printf '%s\n' "FATAL: if you set AIRFLOW__CORE__SQL_ALCHEMY_CONN manually with CeleryExecutor you must also set AIRFLOW__CELERY__RESULT_BACKEND"
      exit 1
    fi

    # Derive useful variables from the AIRFLOW__ variables provided explicitly by the user
    POSTGRES_ENDPOINT=$(echo -n "$AIRFLOW__CORE__SQL_ALCHEMY_CONN" | cut -d '/' -f3 | sed -e 's,.*@,,')
    AIRFLOW_DB_HOST=$(echo -n "$POSTGRES_ENDPOINT" | cut -d ':' -f1)
    AIRFLOW_DB_PORT=$(echo -n "$POSTGRES_ENDPOINT" | cut -d ':' -f2)
  fi

# CeleryExecutor drives the need for a Celery broker, here Redis is used
if [ "$AIRFLOW__CORE__EXECUTOR" = "CeleryExecutor" ]; then
  # Check if the user has provided explicit Airflow configuration concerning the broker
  if [ -z "$AIRFLOW__CELERY__BROKER_URL" ]; then
    # Default values corresponding to the default compose files
    : "${REDIS_PROTO:="redis://"}"
    : "${REDIS_HOST:="redis"}"
    : "${REDIS_PORT:="6379"}"
    : "${REDIS_PASSWORD:=""}"
    : "${REDIS_DBNUM:="1"}"

    # When Redis is secured by basic auth, it does not handle the username part of basic auth, only a token
    if [ -n "$REDIS_PASSWORD" ]; then
      REDIS_PREFIX=":${REDIS_PASSWORD}@"
    else
      REDIS_PREFIX=
    fi

    AIRFLOW__CELERY__BROKER_URL="${REDIS_PROTO}${REDIS_PREFIX}${REDIS_HOST}:${REDIS_PORT}/${REDIS_DBNUM}"
    export AIRFLOW__CELERY__BROKER_URL
  else
    # Derive useful variables from the AIRFLOW__ variables provided explicitly by the user
    REDIS_ENDPOINT=$(echo -n "$AIRFLOW__CELERY__BROKER_URL" | cut -d '/' -f3 | sed -e 's,.*@,,')
    REDIS_HOST=$(echo -n "$POSTGRES_ENDPOINT" | cut -d ':' -f1)
    REDIS_PORT=$(echo -n "$POSTGRES_ENDPOINT" | cut -d ':' -f2)
  fi
fi

# Make cornflow connection for response from workers
  if [ -z "$AIRFLOW_CONN_CF_URI" ]; then
    # Default values corresponding to the default compose files
    : "${CORNFLOW_HOST:="cornflow"}"
    : "${CORNFLOW_PORT:="5000"}"
    export \
    CORNFLOW_HOST \
    CORNFLOW_PORT
    # Make the uri connection to get back response from airflow
    AIRFLOW_CONN_CF_URI="cornflow://${CORNFLOW_SERVICE_USER}:${CORNFLOW_SERVICE_PWD}@${CORNFLOW_HOST}:${CORNFLOW_PORT}"
    export AIRFLOW_CONN_CF_URI
  fi

# Check LDAP parameters for active directory
if [ "$AIRFLOW_LDAP_ENABLE" = "True" ]; then
  # Default values corresponding to the default compose files
    : "${AIRFLOW_LDAP_URI:="ldap://openldap:389"}"
    : "${AIRFLOW_LDAP_SEARCH:="ou=users,dc=example,dc=org"}"
    : "${AIRFLOW_LDAP_BIND_USER:="cn=admin,dc=example,dc=org"}"
    : "${AIRFLOW_LDAP_UID_FIELD:="cn"}"
    : "${AIRFLOW_LDAP_BIND_PASSWORD:="admin"}"
    : "${AIRFLOW_LDAP_ROLE_MAPPING_ADMIN:="\"cn=administrators,ou=groups,dc=example,dc=org\""}"
    : "${AIRFLOW_LDAP_ROLE_MAPPING_OP:="\"cn=services,ou=groups,dc=example,dc=org\""}"
    : "${AIRFLOW_LDAP_ROLE_MAPPING_PUBLIC:="\"cn=viewers,ou=groups,dc=example,dc=org\""}"
    : "${AIRFLOW_LDAP_ROLE_MAPPING_VIEWER:="\"cn=planners,ou=groups,dc=example,dc=org\""}"
    : "${AIRFLOW_LDAP_GROUP_FIELD:="memberUid"}"
    mv "$AIRFLOW_HOME"/webserver_ldap.py "$AIRFLOW_HOME"/webserver_config.py
    export  \
      AIRFLOW_LDAP_URI \
      AIRFLOW_LDAP_SEARCH \
      AIRFLOW_LDAP_BIND_USER \
      AIRFLOW_LDAP_BIND_PASSWORD \
      AIRFLOW_LDAP_UID_FIELD \
      AIRFLOW_LDAP_ROLE_MAPPING_ADMIN \
      AIRFLOW_LDAP_ROLE_MAPPING_OP \
      AIRFLOW_LDAP_ROLE_MAPPING_PUBLIC \
      AIRFLOW_LDAP_ROLE_MAPPING_VIEWER \
      AIRFLOW_LDAP_GROUP_FIELD \
      AIRFLOW_LDAP_USE_TLS \
      AIRFLOW_LDAP_TLS_CA_CERTIFICATE
  # Special condition for using TLS
  if [[ "$AIRFLOW_LDAP_USE_TLS" == "True" ]]; then
    [[ -z "$AIRFLOW_LDAP_TLS_CA_CERTIFICATE" ]] && >&2 printf '%s\n' "FATAL: if you set AIRFLOW_LDAP_USE_TLS you must also set AIRFLOW_LDAP_TLS_CA_CERTIFICATE"
       exit 1
       fi
  fi

case "$1" in
  webserver)
    airflow db init
    # Create user only if using AUTH_DB
    if [ -z "$AIRFLOW_LDAP_BIND_USER" ]; then
    airflow users create \
      --username "$AIRFLOW_USER" \
      --firstname "$AIRFLOW_FIRSTNAME" \
      --lastname "$AIRFLOW_LASTNAME" \
      --role "$AIRFLOW_ROLE" \
      --password "$AIRFLOW_PWD" \
      --email "$AIRFLOW_USER_EMAIL"
    fi
    if [ "$AIRFLOW__CORE__EXECUTOR" = "LocalExecutor" ] || [ "$AIRFLOW__CORE__EXECUTOR" = "SequentialExecutor" ]; then
      # With the "Local" and "Sequential" executors it should all run in one container.
      airflow scheduler &
    fi
    exec airflow webserver
    ;;
  worker)
    # Give the webserver time to run initdb.
    sleep 10
    exec airflow celery "$@"
    ;;
  scheduler)
    sleep 10
    exec airflow "$@"
    ;;
  flower)
    sleep 10
    exec airflow celery "$@" --basic-auth="$AIRFLOW_USER":"$AIRFLOW_PWD"
    ;;
  version)
    exec airflow "$@"
    ;;
  *)
    # The command is something like bash, not an airflow subcommand. Just run it in the right environment.
    exec "$@"
    ;;
esac
