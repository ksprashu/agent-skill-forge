Read this during manual review (step 4) for fix guidance, and when emitting findings (step 6) to pick the `references[]` URL that tells the author how to fix the issue.

# OWASP Cheat Sheet Series index, by topic and language

Home: <https://cheatsheetseries.owasp.org/>. Full alphabetical list: <https://cheatsheetseries.owasp.org/Glossary.html>. Indexes keyed to other standards: Top 10 <https://cheatsheetseries.owasp.org/IndexTopTen.html>, ASVS <https://cheatsheetseries.owasp.org/IndexASVS.html>.

All URLs below follow `https://cheatsheetseries.owasp.org/cheatsheets/<Name>.html` and were checked live on 2026-10-24. One cheat sheet per finding is usually enough: cite the one with the concrete fix, not the broadest one.

## By topic

### Injection and output encoding
- SQL Injection Prevention: <https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html>
- Query Parameterization (examples in many languages): <https://cheatsheetseries.owasp.org/cheatsheets/Query_Parameterization_Cheat_Sheet.html>
- Injection Prevention (general): <https://cheatsheetseries.owasp.org/cheatsheets/Injection_Prevention_Cheat_Sheet.html>
- OS Command Injection Defense: <https://cheatsheetseries.owasp.org/cheatsheets/OS_Command_Injection_Defense_Cheat_Sheet.html>
- LDAP Injection Prevention: <https://cheatsheetseries.owasp.org/cheatsheets/LDAP_Injection_Prevention_Cheat_Sheet.html>
- NoSQL Security: <https://cheatsheetseries.owasp.org/cheatsheets/NoSQL_Security_Cheat_Sheet.html>
- Server-Side Template Injection Prevention: <https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Template_Injection_Prevention_Cheat_Sheet.html>
- Cross-Site Scripting Prevention: <https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html>
- DOM-based XSS Prevention: <https://cheatsheetseries.owasp.org/cheatsheets/DOM_based_XSS_Prevention_Cheat_Sheet.html>
- Prototype Pollution Prevention: <https://cheatsheetseries.owasp.org/cheatsheets/Prototype_Pollution_Prevention_Cheat_Sheet.html>
- XML External Entity Prevention: <https://cheatsheetseries.owasp.org/cheatsheets/XML_External_Entity_Prevention_Cheat_Sheet.html>
- Deserialization: <https://cheatsheetseries.owasp.org/cheatsheets/Deserialization_Cheat_Sheet.html>
- Input Validation: <https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html>

### Authentication, sessions and tokens
- Authentication: <https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html>
- Password Storage: <https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html>
- Forgot Password: <https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html>
- Multifactor Authentication: <https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html>
- Credential Stuffing Prevention: <https://cheatsheetseries.owasp.org/cheatsheets/Credential_Stuffing_Prevention_Cheat_Sheet.html>
- Session Management: <https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html>
- JSON Web Token: <https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_Cheat_Sheet.html>
- OAuth 2.0: <https://cheatsheetseries.owasp.org/cheatsheets/OAuth2_Cheat_Sheet.html>
- SAML Security: <https://cheatsheetseries.owasp.org/cheatsheets/SAML_Security_Cheat_Sheet.html>

### Authorization and access control
- Authorization: <https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html>
- Insecure Direct Object Reference Prevention: <https://cheatsheetseries.owasp.org/cheatsheets/Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet.html>
- Multi-Tenant Security: <https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html>
- Mass Assignment: <https://cheatsheetseries.owasp.org/cheatsheets/Mass_Assignment_Cheat_Sheet.html>
- Cross-Site Request Forgery Prevention: <https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html>
- Unvalidated Redirects and Forwards: <https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html>
- Transaction Authorization: <https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html>

### Requests, files and network
- Server-Side Request Forgery Prevention: <https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html>
- File Upload: <https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html>
- Webhook Security: <https://cheatsheetseries.owasp.org/cheatsheets/Webhook_Security_Cheat_Sheet.html>
- REST Security: <https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html>
- GraphQL: <https://cheatsheetseries.owasp.org/cheatsheets/GraphQL_Cheat_Sheet.html>
- WebSocket Security: <https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html>
- Denial of Service: <https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html>

### Browser and headers
- HTTP Headers: <https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html>
- Content Security Policy: <https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html>
- HTTP Strict Transport Security: <https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Strict_Transport_Security_Cheat_Sheet.html>
- Clickjacking Defense: <https://cheatsheetseries.owasp.org/cheatsheets/Clickjacking_Defense_Cheat_Sheet.html>
- Third Party JavaScript Management: <https://cheatsheetseries.owasp.org/cheatsheets/Third_Party_Javascript_Management_Cheat_Sheet.html>

### Crypto, secrets and data
- Cryptographic Storage: <https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html>
- Key Management: <https://cheatsheetseries.owasp.org/cheatsheets/Key_Management_Cheat_Sheet.html>
- Secrets Management: <https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html>
- Transport Layer Security: <https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Security_Cheat_Sheet.html>
- User Privacy Protection: <https://cheatsheetseries.owasp.org/cheatsheets/User_Privacy_Protection_Cheat_Sheet.html>

### Logging and errors
- Logging: <https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html>
- Logging Vocabulary: <https://cheatsheetseries.owasp.org/cheatsheets/Logging_Vocabulary_Cheat_Sheet.html>
- Error Handling: <https://cheatsheetseries.owasp.org/cheatsheets/Error_Handling_Cheat_Sheet.html>

### Supply chain, CI/CD and infrastructure
- Software Supply Chain Security: <https://cheatsheetseries.owasp.org/cheatsheets/Software_Supply_Chain_Security_Cheat_Sheet.html>
- Vulnerable Dependency Management: <https://cheatsheetseries.owasp.org/cheatsheets/Vulnerable_Dependency_Management_Cheat_Sheet.html>
- Dependency Graph and SBOM: <https://cheatsheetseries.owasp.org/cheatsheets/Dependency_Graph_SBOM_Cheat_Sheet.html>
- NPM Security: <https://cheatsheetseries.owasp.org/cheatsheets/NPM_Security_Cheat_Sheet.html>
- CI/CD Security: <https://cheatsheetseries.owasp.org/cheatsheets/CI_CD_Security_Cheat_Sheet.html>
- GitHub Actions Security: <https://cheatsheetseries.owasp.org/cheatsheets/GitHub_Actions_Security_Cheat_Sheet.html>
- Docker Security: <https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html>
- Kubernetes Security: <https://cheatsheetseries.owasp.org/cheatsheets/Kubernetes_Security_Cheat_Sheet.html>
- Infrastructure as Code Security: <https://cheatsheetseries.owasp.org/cheatsheets/Infrastructure_as_Code_Security_Cheat_Sheet.html>

### Design and review
- Threat Modeling: <https://cheatsheetseries.owasp.org/cheatsheets/Threat_Modeling_Cheat_Sheet.html>
- Abuse Case: <https://cheatsheetseries.owasp.org/cheatsheets/Abuse_Case_Cheat_Sheet.html>
- Attack Surface Analysis: <https://cheatsheetseries.owasp.org/cheatsheets/Attack_Surface_Analysis_Cheat_Sheet.html>
- Secure Code Review: <https://cheatsheetseries.owasp.org/cheatsheets/Secure_Code_Review_Cheat_Sheet.html>
- Business Logic Security: <https://cheatsheetseries.owasp.org/cheatsheets/Business_Logic_Security_Cheat_Sheet.html>

### AI, LLM and agents
- LLM Prompt Injection Prevention: <https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html>
- AI Agent Security: <https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html>
- Secure Coding with AI: <https://cheatsheetseries.owasp.org/cheatsheets/Secure_Coding_with_AI_Cheat_Sheet.html>
- RAG Security: <https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html>
- MCP Security: <https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html>

## By language and framework

| Language / stack | Cheat sheets |
|---|---|
| Java | Java Security <https://cheatsheetseries.owasp.org/cheatsheets/Java_Security_Cheat_Sheet.html>; Injection Prevention in Java <https://cheatsheetseries.owasp.org/cheatsheets/Injection_Prevention_in_Java_Cheat_Sheet.html>; Bean Validation <https://cheatsheetseries.owasp.org/cheatsheets/Bean_Validation_Cheat_Sheet.html>; JAAS <https://cheatsheetseries.owasp.org/cheatsheets/JAAS_Cheat_Sheet.html> |
| JavaScript / TypeScript | JavaScript and TypeScript Security <https://cheatsheetseries.owasp.org/cheatsheets/JavaScript_and_TypeScript_Security_Cheat_Sheet.html>; Node.js Security <https://cheatsheetseries.owasp.org/cheatsheets/Nodejs_Security_Cheat_Sheet.html>; Next.js Security <https://cheatsheetseries.owasp.org/cheatsheets/Nextjs_Security_Cheat_Sheet.html>; NPM Security (above); Node.js Docker <https://cheatsheetseries.owasp.org/cheatsheets/NodeJS_Docker_Cheat_Sheet.html> |
| Python | Django Security <https://cheatsheetseries.owasp.org/cheatsheets/Django_Security_Cheat_Sheet.html>; Django REST Framework <https://cheatsheetseries.owasp.org/cheatsheets/Django_REST_Framework_Cheat_Sheet.html>; FastAPI Security <https://cheatsheetseries.owasp.org/cheatsheets/FastAPI_Security_Cheat_Sheet.html> |
| .NET | DotNet Security <https://cheatsheetseries.owasp.org/cheatsheets/DotNet_Security_Cheat_Sheet.html> |
| PHP | PHP Configuration <https://cheatsheetseries.owasp.org/cheatsheets/PHP_Configuration_Cheat_Sheet.html>; Laravel <https://cheatsheetseries.owasp.org/cheatsheets/Laravel_Cheat_Sheet.html>; Symfony <https://cheatsheetseries.owasp.org/cheatsheets/Symfony_Cheat_Sheet.html> |
| Ruby | Ruby on Rails <https://cheatsheetseries.owasp.org/cheatsheets/Ruby_on_Rails_Cheat_Sheet.html> |
| Go, Rust | No language-specific cheat sheet in the series at check time. Use the topic sheets above; Query Parameterization and OS Command Injection Defense apply directly. For Go vulnerability tooling see <https://go.dev/doc/security/vuln/>. |
| C / C++ | C-Based Toolchain Hardening <https://cheatsheetseries.owasp.org/cheatsheets/C-Based_Toolchain_Hardening_Cheat_Sheet.html> |
| gRPC | gRPC Security <https://cheatsheetseries.owasp.org/cheatsheets/gRPC_Security_Cheat_Sheet.html> |
| Mobile | Mobile Application Security <https://cheatsheetseries.owasp.org/cheatsheets/Mobile_Application_Security_Cheat_Sheet.html> |

## Picking a reference for a finding

1. Specific fix sheet first (SQL Injection Prevention for CWE-89, not Injection Prevention).
2. Then the language or framework sheet if it shows the idiomatic fix (Django's ORM, Spring's `JdbcTemplate`).
3. Then the CWE definition page (`https://cwe.mitre.org/data/definitions/<n>.html`) if no sheet fits.
4. Every `references[]` URL must be `https://` (the schema rejects anything else).
