"""Brazilian Portuguese catalogue: English source text -> translation."""

STRINGS = {
    # -- app / configuration ----------------------------------------------------
    "Invalid configuration": "Configuração inválida",
    "File '{name}' not found in {folder}.": "Arquivo '{name}' não encontrado em {folder}.",
    "{where}: required field '{key}' is missing.": "{where}: campo obrigatório '{key}' ausente.",
    "server.protocol must be 'ftp' or 'ftps'.": "server.protocol deve ser 'ftp' ou 'ftps'.",
    "server: set 'host' or 'credentials_url'.": "server: informe 'host' ou 'credentials_url'.",
    "auth.type must be 'none' or 'http'.": "auth.type deve ser 'none' ou 'http'.",
    "{where}: type must be 'bool', 'text' or 'password'.": "{where}: type deve ser 'bool', 'text' ou 'password'.",
    "{where}: id '{id}' may only contain letters, digits, '-', '_' or '.'.":
        "{where}: id '{id}' deve conter apenas letras, números, '-', '_' ou '.'.",
    "{where}: duplicate option keys.": "{where}: chaves de options repetidas.",
    "The configuration file must contain a JSON object.": "O arquivo de configuração deve conter um objeto JSON.",
    "Configure at least one application in 'apps'.": "Configure ao menos um aplicativo em 'apps'.",
    "Some applications share the same 'id'.": "Há aplicativos com o mesmo 'id'.",
    "accent_color must be in the #RRGGBB format.": "accent_color deve estar no formato #RRGGBB.",
    "Could not read {path}: {error}": "Não foi possível ler {path}: {error}",
    "Invalid JSON in {name} (line {line}, column {column}): {error}":
        "JSON inválido em {name} (linha {line}, coluna {column}): {error}",
    "{where} must be an object.": "{where} deve ser um objeto.",
    "{where}: '{key}' must be a text or an object of translations.":
        "{where}: '{key}' deve ser um texto ou um objeto com traduções.",
    "{where}: github must be in the 'owner/repository' format.":
        "{where}: github deve estar no formato 'dono/repositório'.",
    "{where}: {key} must be a path inside the install folder.":
        "{where}: {key} deve ser um caminho dentro da pasta de instalação.",
    "{where}: {key} must be in the #RRGGBB format.": "{where}: {key} deve estar no formato #RRGGBB.",
    "'github' must be an object.": "'github' deve ser um objeto.",

    # -- core: auth / remote / installer ------------------------------------------
    "Could not sign in automatically. Check your username and password.":
        "Não foi possível entrar automaticamente. Verifique usuário e senha.",
    "Automatic sign-in failed:\n{error}": "Falha na autenticação automática:\n{error}",
    "Executable not found: {name}": "Executável não encontrado: {name}",
    "Unsafe zip entry: {name}": "Entrada insegura no zip: {name}",
    "Unsafe zip entry (outside the destination): {name}": "Entrada insegura no zip (fora do destino): {name}",
    "Credentials JSON has no 'host'.": "JSON de credenciais sem 'host'.",
    "password_enc is set, but server.secret is empty.": "password_enc informado, mas server.secret está vazio.",
    "Could not get the server credentials and there are no saved credentials on this machine. "
    "Check your internet connection.":
        "Não foi possível obter as credenciais do servidor e não há credenciais salvas nesta máquina. "
        "Verifique a conexão com a internet.",
    "{name} exceeds {max} bytes": "{name} excede {max} bytes",
    "The SHA-256 of {name} does not match the one published on the server.":
        "O SHA-256 de {name} não confere com o publicado no servidor.",

    "Incomplete download of {name}: {done} of {total} bytes.":
        "Download incompleto de {name}: {done} de {total} bytes.",
    "Could not replace {name}: the file is in use. Close the application and try again.":
        "Não foi possível substituir {name}: o arquivo está em uso. Feche o aplicativo e tente de novo.",
    "The package of {name} has no .exe file.": "O pacote de {name} não tem nenhum arquivo .exe.",
    "{name} cannot be installed: only .zip and .exe files are supported.":
        "{name} não pode ser instalado: só arquivos .zip e .exe são suportados.",

    # -- GitHub -----------------------------------------------------------------
    "GitHub's request limit was reached. Try again after {time}.":
        "O limite de consultas ao GitHub foi atingido. Tente de novo depois das {time}.",
    "GitHub rejected the configured token (401).": "O GitHub recusou o token configurado (401).",
    "{what} was not found on GitHub (or it is private).": "{what} não foi encontrado no GitHub (ou é privado).",
    "GitHub answered with an error ({status}) for {what}.": "O GitHub respondeu com erro ({status}) para {what}.",
    "Could not reach GitHub: {error}": "Não foi possível acessar o GitHub: {error}",
    "The SHA-256 of {name} does not match the one published on GitHub.":
        "O SHA-256 de {name} não confere com o publicado no GitHub.",
    "No release has been published yet.": "Nenhuma versão foi publicada ainda.",
    "No release has a file matching “{pattern}”.": "Nenhuma versão tem um arquivo que corresponda a “{pattern}”.",
    "No release has a Windows file (.zip or .exe).": "Nenhuma versão tem um arquivo para Windows (.zip ou .exe).",

    "Invalid secret: base64 expected": "Segredo inválido: esperado base64",
    "Secret too short (minimum 16 bytes)": "Segredo curto demais (mínimo 16 bytes)",
    "Invalid base64 token: {error}": "Token base64 inválido: {error}",
    "Unrecognised token format": "Formato de token não reconhecido",
    "Invalid HMAC — wrong secret or tampered token": "HMAC inválido — segredo incorreto ou token adulterado",

    # -- shared -----------------------------------------------------------------
    "OK": "OK",
    "Cancel": "Cancelar",
    "Confirm": "Confirmar",
    "Close": "Fechar",
    "Minimize": "Minimizar",
    "Loading…": "Carregando…",
    "Install": "Instalar",
    "Update": "Atualizar",
    "Not now": "Agora não",
    "Replace": "Substituir",

    # -- main window --------------------------------------------------------------
    "Home": "Início",
    "Release notes": "Notas de versão",
    "Issues": "Issues",
    "Website": "Site",
    "LIBRARY": "BIBLIOTECA",
    "Latest": "Mais recente",
    "Size": "Tamanho",
    "Launch": "Abrir",
    "Downloading": "Baixando",
    "Installing": "Instalando",
    "Running": "Em execução",
    "Not installed": "Não instalado",
    "Unknown version": "Versão desconhecida",
    "an unknown version": "uma versão desconhecida",
    "Checking…": "Verificando…",
    "Unavailable": "Indisponível",
    "Update · {version}": "Atualizar · {version}",
    "Downloading · {percent}%": "Baixando · {percent}%",
    "Ready to launch.": "Pronto para abrir.",
    "{name} is running.": "{name} está em execução.",
    "{version} is ready to install.": "{version} está pronto para instalar.",
    "Update available: {new} (you have {old}).": "Atualização disponível: {new} (você tem {old}).",
    "Checking for the latest version…": "Procurando a versão mais recente…",
    "Waiting for {name} to finish installing.": "Aguardando {name} terminar de instalar.",
    "(offline: showing saved information)": "(offline: mostrando as informações salvas)",
    "Installed in {path}": "Instalado em {path}",
    "Will be installed in {path}": "Será instalado em {path}",
    "Connecting…": "Conectando…",
    "Downloading {name} {version}…": "Baixando {name} {version}…",
    "Installing {name}…": "Instalando {name}…",
    "{time} left": "faltam {time}",
    "{name} {version} installed.": "{name} {version} instalado.",
    "Download cancelled.": "Download cancelado.",
    "Cancelling…": "Cancelando…",
    "Close {name} before updating it.": "Feche o {name} antes de atualizá-lo.",
    "Launch without updating": "Abrir sem atualizar",
    "Options of {name}": "Opções do {name}",
    "Offline": "Offline",
    "Archived": "Arquivado",
    "WHAT'S NEW · {version}": "NOVIDADES · {version}",
    "RELEASES · {count}": "VERSÕES · {count}",
    "REPOSITORY": "REPOSITÓRIO",
    "{count} open issues": "{count} issues abertas",
    "Open on GitHub": "Abrir no GitHub",
    "No release notes.": "Sem notas de versão.",
    "*No release notes.*": "*Sem notas de versão.*",
    "No release notes for this application.": "Este aplicativo não tem notas de versão.",
    "View on GitHub": "Ver no GitHub",
    "LATEST": "MAIS RECENTE",
    "INSTALLED": "INSTALADO",
    "PRE-RELEASE": "PRÉ-VERSÃO",
    "Settings": "Configurações",
    "Downloads": "Downloads",
    "Report a bug": "Relatar um bug",
    "Installed": "Instalado",
    "Check for updates": "Verificar atualizações",
    "More options": "Mais opções",
    "Ready.": "Pronto.",
    "Signed in as {user}": "Conectado como {user}",
    "using the example configuration": "usando a configuração de exemplo",
    "Connecting to the server…": "Conectando ao servidor…",
    "All good · you already have the latest version.": "Tudo certo · você já tem a versão mais recente.",
    "Installing…": "Instalando…",
    "Verify integrity": "Verificar integridade",
    "Open install folder": "Abrir pasta de instalação",
    "Uninstall": "Desinstalar",
    "Install folder": "Pasta de instalação",
    "found": "presente",
    "not found": "ausente",
    "missing": "ausente",
    "Executable <i>{name}</i>": "Executável <i>{name}</i>",
    "Version record": "Registro da versão",
    "Files in folder: <b>{count}</b>": "Arquivos na pasta: <b>{count}</b>",
    "Integrity check": "Verificação de integridade",
    "Uninstall <b>{name}</b>?<br><br>All files in<br><i>{path}</i><br>will be deleted.":
        "Desinstalar <b>{name}</b>?<br><br>Todos os arquivos em<br><i>{path}</i><br>serão apagados.",
    "Could not remove the files:<br>{error}": "Não foi possível remover os arquivos:<br>{error}",
    "{name} was uninstalled.": "{name} foi desinstalado.",
    "Open application": "Abrir aplicativo",
    "Operation in progress": "Operação em andamento",
    "A download or installation is in progress. Close anyway?":
        "Há um download ou instalação em andamento. Fechar mesmo assim?",

    # -- launcher self-update -----------------------------------------------------
    "Launcher update": "Atualização do launcher",
    "The new version was downloaded, but the executable could not be replaced.<br><br>"
    "This usually happens when another launcher window is open, an antivirus blocks the swap, "
    "or the folder is not writable. Close the other instances and open the launcher again.":
        "A nova versão foi baixada, mas o executável não pôde ser substituído.<br><br>"
        "Isso costuma acontecer com outra janela do launcher aberta, antivírus bloqueando a troca "
        "ou pasta sem permissão de escrita. Feche as outras instâncias e abra o launcher de novo.",
    "A new launcher version is available (<b>{version}</b>).<br><br>"
    "Update now? The launcher will restart.":
        "Há uma nova versão do launcher (<b>{version}</b>).<br><br>"
        "Atualizar agora? O launcher será reiniciado.",
    "Downloading the new launcher version…": "Baixando a nova versão do launcher…",
    "Restarting to apply the update…": "Reiniciando para aplicar a atualização…",

    # -- downloads ----------------------------------------------------------------
    "Select all": "Marcar todos",
    "Clear selection": "Limpar seleção",
    "Open folder": "Abrir pasta",
    "Download selected": "Baixar selecionados",
    "Download {count} file(s)": "Baixar {count} arquivo(s)",
    "Destination: {path}": "Destino: {path}",
    "FILE": "ARQUIVO",
    "SIZE": "TAMANHO",
    "MODIFIED": "MODIFICADO",
    "Listing files…": "Listando arquivos…",
    "Could not load the list.": "Não foi possível carregar a lista.",
    "Could not list the files:<br>{error}": "Não foi possível listar os arquivos:<br>{error}",
    "{count} file(s) available.": "{count} arquivo(s) disponível(is).",
    "No files available in this tab.": "Nenhum arquivo disponível nesta aba.",
    "… and {count} more": "… e mais {count}",
    "Replace files?": "Substituir arquivos?",
    "These files already exist and will be replaced:<br><br>{names}{more}":
        "Estes arquivos já existem e serão substituídos:<br><br>{names}{more}",
    "Downloading {n}/{total}: {name}": "Baixando {n}/{total}: {name}",
    "{ok} downloaded, {failed} failed.": "{ok} baixado(s), {failed} com erro.",
    "Partial download": "Download parcial",
    "<b>{ok}</b> file(s) downloaded.<br><br>Failures:<br>{lines}":
        "<b>{ok}</b> arquivo(s) baixado(s).<br><br>Falhas:<br>{lines}",
    "{ok} file(s) saved to {path}.": "{ok} arquivo(s) salvo(s) em {path}.",
    "The download failed:<br>{error}": "Falha durante o download:<br>{error}",

    # -- login --------------------------------------------------------------------
    "Sign in": "Entrar",
    "Sign in to continue to {name}.": "Acesse para continuar no {name}.",
    "Username": "Usuário",
    "Password": "Senha",
    "Remember me on this computer": "Lembrar meus dados neste computador",
    "Enter your username and password.": "Preencha usuário e senha.",
    "Verifying…": "Verificando…",
    "Invalid username or password.": "Usuário ou senha inválidos.",
    "Authentication failed: {error}": "Falha na autenticação: {error}",

    # -- settings -----------------------------------------------------------------
    "GENERAL": "GERAL",
    "OPTIONS · {name}": "OPÇÕES · {name}",
    "Update applications on startup": "Atualizar aplicativos ao abrir",
    "Installs new versions of the installed applications by itself.":
        "Instala sozinho as versões novas dos aplicativos instalados.",
    "Update the launcher on startup": "Atualizar o launcher ao abrir",
    "Without this option, the launcher asks before updating itself.":
        "Sem esta opção, o launcher pergunta antes de se atualizar.",
    "Keep the launcher open": "Manter o launcher aberto",
    "By default the launcher closes after starting an application.":
        "Por padrão o launcher fecha depois de iniciar um aplicativo.",
    "Sign in automatically": "Entrar automaticamente",
    "Uses the saved credentials and skips the login screen.":
        "Usa as credenciais salvas e pula a tela de login.",
    "Language": "Idioma",
    "Automatic": "Automático",
    "Takes effect the next time the launcher starts.": "Vale a partir da próxima abertura do launcher.",
}
