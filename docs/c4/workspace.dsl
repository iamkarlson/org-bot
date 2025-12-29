workspace "Org Bot" "Architecture model for Org Bot system" {

    model {
        user = person "Beatiful you" "Telegram user interacting with the bot"

        terraform = softwareSystem "Terraform" "IaC for provisioning and managing cloud resources"

        orgBot = softwareSystem "Org Bot" "Telegram bot for managing org-mode notes and journal entries" {

            main = container "Main" "Entry point for the bot application" "Python" {
                tags "Container"

                httpEntrypoint = component "HTTP Entrypoint" "GCP Cloud Function handler for incoming webhooks" "Python" {
                    tags "Component"
                }

                botInitializer = component "Bot Initializer" "Creates and manages bot instances" "Python" {
                    tags "Component"
                }

                messageHandler = component "Message Handler" "Handles incoming Telegram messages" "Python" {
                    tags "Component"
                }

                messageProcessor = component "Message Processor" "Processes commands and non-command messages" "Python" {
                    tags "Component"
                }

                messageSender = component "Message Sender" "Sends responses back to Telegram" "Python" {
                    tags "Component"
                }

                sentryInit = component "Sentry Initialization" "Initializes error tracking" "Python" {
                    tags "Component"
                }
            }

            config = container "Config" "Configuration management" "Python" {
                tags "Container"

                commandInit = component "Command Initialization" "Initializes bot commands" "Python" {
                    tags "Component"
                }

                actionConfig = component "Action Configuration" "Configures journal, todo, and reply actions" "Python" {
                    tags "Component"
                }

                envConfig = component "Environment Configuration" "Loads environment variables" "Python" {
                    tags "Component"
                }
            }

            auth = container "Auth" "Authentication and authorization" "Python" {
                tags "Container"

                authCheck = component "Authorization Check" "Validates if message comes from authorized chat" "Python" {
                    tags "Component"
                }

                ignoreCheck = component "Ignore Check" "Checks if message comes from ignored chat" "Python" {
                    tags "Component"
                }

                unauthorizedForwarder = component "Unauthorized Forwarder" "Forwards unauthorized messages to admin" "Python" {
                    tags "Component"
                }
            }

            orgApi = container "Org API" "API for org-mode operations" "Python" {
                tags "Container"

                entryFinder = component "Entry Finder" "Finds entries in org files by message links" "Python" {
                    tags "Component"
                }

                topLevelFinder = component "Top Level Finder" "Finds top-level non-reply entries" "Python" {
                    tags "Component"
                }

                replyInserter = component "Reply Inserter" "Inserts replies at correct org hierarchy position" "Python" {
                    tags "Component"
                }

                fileCreator = component "File Creator" "Creates new files in repository" "Python" {
                    tags "Component"
                }

                textAppender = component "Text Appender" "Appends text to org files" "Python" {
                    tags "Component"
                }
            }

            utils = container "Utils" "Utility functions" "Python" {
                tags "Container"

                messageTextExtractor = component "Message Text Extractor" "Extracts text from various message types" "Python" {
                    tags "Component"
                }
            }

            baseCommand = container "Base Command" "Base class for bot commands" "Python" {
                tags "Container"

                commandBase = component "Command Base" "Abstract base class for all commands" "Python" {
                    tags "Component"
                }
            }

            commands = container "Commands" "Bot command handlers module" "Python" {
                tags "Module"

                startCommand = component "Start Command" "Handles /start command" "Python" {
                    tags "Component"
                }

                infoCommand = component "Info Command" "Handles /info command" "Python" {
                    tags "Component"
                }

                webhookCommand = component "Webhook Command" "Handles webhook operations" "Python" {
                    tags "Component"
                }

            }

            actions = container "Actions" "Journal, todo, and reply actions module" "Python" {
                tags "Module"
                postToJournal = component "Post to Journal" "Handles posting entries to journal" "Python" {
                    tags "Component"
                }

                postToTodo = component "Post to Todo" "Handles posting entries to todo list" "Python" {
                    tags "Component"
                }

                postReply = component "Post Reply" "Handles posting replies to entries" "Python" {
                    tags "Component"
                }
            }

            tracing = container "Tracing" "Logging and tracing module" "Python" {
                tags "Module"

                gcp_log = component "Log" "Logging utilities" "Python" {
                    tags "Component"
                }
            }
        }

        # Relationships - System Level
        user -> orgBot "Interacts with"
        orgBot -> terraform "Deployed using"

        # Relationships - Container Level
        main -> commands
        main -> config "Get / commands"
        main -> config "Get actions"
        main -> auth
        main -> orgApi
        main -> utils
        main -> gcp_log "Configure GCP structured logging"

        commands -> baseCommand "Extends"
        commands -> tracing "Uses for logging"
        commands -> orgApi

        startCommand -> baseCommand "Extends"
        infoCommand -> baseCommand "Extends"
        webhookCommand -> baseCommand "Extends"
        postToJournal -> baseCommand "Extends"


        orgApi -> config
        auth -> config

        # Relationships - Component Level (Main)
        httpEntrypoint -> messageHandler "Delegates to"
        messageHandler -> authCheck "Checks authorization"
        messageHandler -> messageProcessor "Processes message"
        messageProcessor -> commandInit "Gets commands"
        messageProcessor -> actionConfig "Gets actions"
        messageProcessor -> messageTextExtractor "Extracts text"
        messageHandler -> messageSender "Sends response"
        messageSender -> botInitializer "Gets bot instance"

        # Relationships - Component Level (Config)
        commandInit -> envConfig
        actionConfig -> envConfig

        # Relationships - Component Level (Auth)
        authCheck -> envConfig
        authCheck -> unauthorizedForwarder "Forwards unauthorized"
        ignoreCheck -> envConfig

        # Relationships - Component Level (Org API)
        entryFinder -> topLevelFinder "Finds parent"
        replyInserter -> entryFinder
        replyInserter -> topLevelFinder
        textAppender -> fileCreator "May create file"

        # Relationships - Component Level (Commands)
        startCommand -> commandBase "Extends"
        infoCommand -> commandBase "Extends"
        webhookCommand -> commandBase "Extends"
        postToJournal -> commandBase "Extends"
        postToJournal -> textAppender
        postToJournal -> replyInserter
    }

    views {
        systemContext orgBot "SystemContext" {
            include *
        }

        container orgBot "Containers" {
            include *
        }

        component main "MainComponents" {
            include *
        }

        component config "ConfigComponents" {
            include *
        }

        component auth "AuthComponents" {
            include *
        }

        component orgApi "OrgApiComponents" {
            include *
        }

        component utils "UtilsComponents" {
            include *
        }

        component baseCommand "BaseCommandComponents" {
            include *
        }

        component commands "CommandsComponents" {
            include *
        }

        component tracing "TracingComponents" {
            include *
        }

        styles {
            element "Software System" {
                background #1168bd
                color #ffffff
            }
            element "Container" {
                background #438dd5
                color #ffffff
            }
            element "Module" {
                background #85bbf0
                color #000000
            }
            element "Component" {
                background #a5c9f5
                color #000000
            }
            element "Person" {
                shape person
                background #08427b
                color #ffffff
            }
        }

        theme https://static.structurizr.com/themes/google-cloud-platform-v1.5/theme.json

    }

}
