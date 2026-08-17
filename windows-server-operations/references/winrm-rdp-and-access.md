# WinRM, RDP, and access safety

Before modifying remote access, confirm a second management path: Hyper-V/VM console, iLO/DRAC, or a second proven WinRM/RDP session. Record current firewall rules, WinRM listener/certificate/authentication posture, Network Level Authentication for RDP, and intended operator groups.

Use encrypted WinRM (HTTPS) where practical; do not enable Basic authentication, TrustedHosts wildcards, or broad RDP exposure as a convenience. Do not copy passwords, private keys, or tokens into scripts, profiles, or ledgers. Local group membership and service accounts require explicit R3 approval in production.