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
    "custom_builds.code_pattern is invalid: {error}": "custom_builds.code_pattern inválido: {error}",
    "Could not read {path}: {error}": "Não foi possível ler {path}: {error}",
    "Invalid JSON in {name} (line {line}, column {column}): {error}":
        "JSON inválido em {name} (linha {line}, coluna {column}): {error}",

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
    "Open": "Abrir",
    "Remove": "Remover",
    "Replace": "Substituir",

    # -- main window --------------------------------------------------------------
    "Settings": "Configurações",
    "Downloads": "Downloads",
    "Help and support": "Ajuda e suporte",
    "APPLICATION": "APLICATIVO",
    "Installed": "Instalado",
    "Available": "Disponível",
    "Check for updates": "Verificar atualizações",
    "More options": "Mais opções",
    "Open {name}": "Abrir {name}",
    "Custom builds ({count})": "Builds personalizadas ({count})",
    "Install update": "Instalar atualização",
    "Not installed. Use “Check for updates” to install.":
        "Não instalado. Use “Verificar atualizações” para instalar.",
    "Ready · updated on {date}": "Pronto · atualizado em {date}",
    "Ready.": "Pronto.",
    "Signed in as {user}": "Conectado como {user}",
    "using the example configuration": "usando a configuração de exemplo",
    "Connecting to the server…": "Conectando ao servidor…",
    "Checking the published version…": "Consultando a versão publicada…",
    "All good · you already have the latest version.": "Tudo certo · você já tem a versão mais recente.",
    "New version available · {date}": "Nova versão disponível · {date}",
    "Version available · {date}": "Versão disponível · {date}",
    "Downloading…": "Baixando…",
    "Installing…": "Instalando…",
    "Updated · version from {date}": "Atualizado · versão de {date}",
    "Installation complete": "Instalação concluída",
    "<b>{name}</b> is ready to use.": "<b>{name}</b> está pronto para uso.",
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
    "Custom builds: <b>{count}</b>": "Builds personalizadas: <b>{count}</b>",
    "Integrity check": "Verificação de integridade",
    "Uninstall <b>{name}</b>?<br><br>All files in<br><i>{path}</i><br>will be deleted. "
    "Custom builds are not affected.":
        "Desinstalar <b>{name}</b>?<br><br>Todos os arquivos em<br><i>{path}</i><br>serão apagados. "
        "Builds personalizadas não são afetadas.",
    "Could not remove the files:<br>{error}": "Não foi possível remover os arquivos:<br>{error}",
    "{name} was uninstalled.": "{name} foi desinstalado.",
    "Open application": "Abrir aplicativo",
    "{name} started.": "{name} iniciado.",
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
    "A new launcher version is available (published on <b>{date}</b>).<br><br>"
    "Update now? The launcher will restart.":
        "Há uma nova versão do launcher (publicada em <b>{date}</b>).<br><br>"
        "Atualizar agora? O launcher será reiniciado.",
    "Downloading the new launcher version…": "Baixando a nova versão do launcher…",
    "Restarting to apply the update…": "Reiniciando para aplicar a atualização…",

    # -- custom builds ------------------------------------------------------------
    "Custom build": "Build personalizada",
    "Build": "Build",
    "Build installed": "Build instalada",
    "Installed builds": "Builds instaladas",
    "Looking for build {code}…": "Procurando a build {code}…",
    "Downloading build {code}…": "Baixando a build {code}…",
    "Build {code} installed.": "Build {code} instalada.",
    "No build found for <b>{label} {code}</b>.<br><br>Check the code and try again.":
        "Nenhuma build encontrada para <b>{label} {code}</b>.<br><br>Confira o código e tente de novo.",
    "Copied from the official installation: {files}": "Copiado da instalação oficial: {files}",
    "Build <b>{code}</b> was installed in a separate folder.<br>Open it from <b>Custom builds</b>.":
        "A build <b>{code}</b> foi instalada numa pasta separada.<br>Abra-a em <b>Builds personalizadas</b>.",
    "How can we help?": "Como podemos ajudar?",
    "Report a problem": "Reportar um problema",
    "Opens the support page in the browser.": "Abre a página de suporte no navegador.",
    "Install custom build": "Instalar build personalizada",
    "Downloads the version prepared for a specific {label}, without touching the official installation.":
        "Baixa a versão preparada para um {label} específico, sem mexer na instalação oficial.",
    "Opens or removes this application's custom builds.":
        "Abre ou remove as builds personalizadas deste aplicativo.",
    "{label} code": "Código do {label}",
    "Enter the code provided by support.": "Informe o código fornecido pelo suporte.",
    "Search": "Buscar",
    "Date": "Data",
    "Base version": "Versão base",
    "Identifier": "Identificador",
    "No description.": "Sem descrição.",
    "A build is already installed for this code (<i>{id}</i>). Installing again replaces that folder.":
        "Já existe uma build instalada para este código (<i>{id}</i>). Instalar de novo substitui essa pasta.",
    "The build is installed in a <b>separate folder</b>, without affecting the official installation "
    "or other builds.":
        "A build é instalada numa <b>pasta separada</b>, sem afetar a instalação oficial nem outras builds.",
    "Choose the build you want to open.": "Escolha a build que deseja abrir.",
    "Remove build": "Remover build",
    "Remove build <b>{code}</b>?<br><br>The files in that folder will be deleted. "
    "Other builds are not affected.":
        "Remover a build <b>{code}</b>?<br><br>Os arquivos dessa pasta serão apagados. "
        "As demais builds não são afetadas.",

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
    "Installs the new version of the selected application by itself, if it is already installed.":
        "Instala sozinho a versão nova do aplicativo selecionado, se ele já estiver instalado.",
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
