{{- define "ledger-py.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "ledger-py.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "ledger-py.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "ledger-py.labels" -}}
app.kubernetes.io/name: {{ include "ledger-py.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end -}}

{{- define "ledger-py.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ledger-py.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/* Common env: non-secret config from the ConfigMap, secrets from the Secret. */}}
{{- define "ledger-py.envFrom" -}}
- configMapRef:
    name: {{ include "ledger-py.fullname" . }}-config
- secretRef:
    name: {{ include "ledger-py.fullname" . }}-secret
{{- end -}}

{{- define "ledger-py.imagePullSecrets" -}}
{{- with .Values.imagePullSecrets }}
imagePullSecrets:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end -}}

{{/*
Shared data blocks. The release ConfigMap/Secret and the hook-scoped copies for
the migration Job (migrate-env.yaml) both render from these so they never drift.
Keys use the LEDGER_ prefix the app reads via pydantic-settings.
*/}}
{{- define "ledger-py.configData" -}}
LEDGER_SERVICE_NAME: {{ .Values.config.serviceName | quote }}
LEDGER_LOG_LEVEL: {{ .Values.config.logLevel | quote }}
LEDGER_TEMPORAL_ADDRESS: {{ .Values.config.temporalAddress | quote }}
LEDGER_TEMPORAL_NAMESPACE: {{ .Values.config.temporalNamespace | quote }}
LEDGER_TEMPORAL_TASK_QUEUE: {{ .Values.config.temporalTaskQueue | quote }}
LEDGER_OTEL_EXPORTER_OTLP_ENDPOINT: {{ .Values.config.otelExporterOtlpEndpoint | quote }}
{{- end -}}

{{- define "ledger-py.secretData" -}}
LEDGER_DATABASE_URL: {{ .Values.secret.databaseUrl | quote }}
LEDGER_API_KEY: {{ .Values.secret.apiKey | quote }}
{{- end -}}
