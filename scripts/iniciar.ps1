# Sobe o Celke Treinar IA Agro no Windows (PowerShell), espera o modelo e mostra o endereço.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\iniciar.ps1
# Sem 'Stop': no PowerShell 5.1, um simples aviso do Docker no stderr viraria erro fatal com *> $null.
# As falhas do Docker sao conferidas pelo $LASTEXITCODE.
$ErrorActionPreference = 'Continue'
Set-Location (Join-Path $PSScriptRoot '..')

docker info *> $null
if ($LASTEXITCODE -ne 0) {
  Write-Host 'O Docker nao esta rodando. Abra o Docker Desktop e tente de novo.'
  exit 1
}

# Senha do PostgreSQL: gerada uma vez e guardada no .env (o banco guarda a senha da primeira subida).
$envFile = Join-Path (Get-Location) '.env'
$lines = @()
if (Test-Path $envFile) { $lines = @(Get-Content $envFile -Encoding UTF8) }
if (-not ($lines | Where-Object { $_ -match '^POSTGRES_PASSWORD=.+' })) {
  $bytes = New-Object byte[] 24
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  $value = -join ($bytes | ForEach-Object { $_.ToString('x2') })
  $lines = @($lines | Where-Object { $_ -notmatch '^POSTGRES_PASSWORD=' }) + "POSTGRES_PASSWORD=$value"
  # UTF-8 sem BOM: o Docker Compose le o .env assim
  [System.IO.File]::WriteAllLines($envFile, [string[]]$lines)
  Write-Host 'POSTGRES_PASSWORD criada no arquivo .env (guarde o arquivo; nao o envie ao git).'
}

Write-Host 'Subindo os servicos (a primeira vez constroi as imagens e pode levar alguns minutos)...'
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { exit 1 }

$services = @(docker compose config --services)
if ($services -contains 'ollama-init') {
  Write-Host 'Aguardando o modelo (o download so acontece na primeira vez; sao de 5 a 9 GB).'
  Write-Host 'Para ver o progresso, em outro terminal: docker compose logs -f ollama-init'
  $status = docker wait celke-treinar-ia-agro-ollama-init-1
  if ($status -ne '0') {
    Write-Host 'Falha ao baixar o modelo. Veja: docker compose logs ollama-init'
    exit 1
  }
} else {
  # compose.externo.yaml: o modelo roda na GPU externa, pelo tunel SSH
  Write-Host 'Modelo na GPU externa: confira o tunel com docker compose logs gpu-tunnel.'
  Write-Host 'O modelo precisa estar baixado no servidor (la: ollama pull <modelo de CHAT_MODEL>).'
}

$port = ((docker compose port frontend 80) -split ':')[-1]
for ($i = 0; $i -lt 30; $i++) {
  docker compose exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)" *> $null
  if ($LASTEXITCODE -eq 0) {
    Write-Host ''
    Write-Host "Pronto! Abra http://localhost:$port"
    Write-Host "Documentacao da API: http://localhost:$port/api/docs"
    Write-Host 'Logs: docker compose logs -f backend    Parar: docker compose stop'
    exit 0
  }
  Start-Sleep -Seconds 2
}
Write-Host 'A API nao respondeu. Veja: docker compose ps; docker compose logs backend'
exit 1
