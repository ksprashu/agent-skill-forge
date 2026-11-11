<!--
Copyright 2026 Google LLC.
SPDX-License-Identifier: Apache-2.0
-->

## Preparing your Workspace (Environment Setup)

Duration: 05:00

Choose either **Google Cloud Shell** in your browser or your **Local Terminal** on your workstation.

### **Option 1: Google Cloud Shell (Browser-Based)**

Cloud Shell is a browser-based terminal pre-installed with [Node.js](https://nodejs.org/), [gcloud CLI](https://cloud.google.com/sdk/gcloud), and [git](https://git-scm.com/).

#### **1. Activate Cloud Shell**

Click the **Activate Cloud Shell** icon in the top-right of your Google Cloud Console. If prompted, click **Authorize** and wait until you see `user@cloudshell:~$`.

#### **2. Verify Your Project**

Confirm your active project ID:

```bash
gcloud config get-value project
```

If it does not show your project ID, set it explicitly:

```bash
gcloud config set project <YOUR-PROJECT-ID>
```

---

### **Option 2: Local Terminal**

If you prefer developing locally, install the required CLI tools first.

#### **1. Install Prerequisites**

*   [Node.js v20+](https://nodejs.org/)
*   [Google Cloud SDK (gcloud CLI)](https://cloud.google.com/sdk/docs/install)

#### **2. Sign In and Configure**

Authenticate with Google Cloud:
```bash
# Copyright 2026 Google LLC.
# SPDX-License-Identifier: Apache-2.0

gcloud auth login
```

Set your active project:

```bash
# Copyright 2026 Google LLC.
# SPDX-License-Identifier: Apache-2.0

gcloud config set project <YOUR-PROJECT-ID>
```

Configure Application Default Credentials so local SDKs can call Google Cloud APIs:

```bash
# Copyright 2026 Google LLC.
# SPDX-License-Identifier: Apache-2.0

gcloud auth application-default login
```

> aside positive
> **Tip:** Keep one terminal tab dedicated to your running dev server and a second tab open for CLI commands and test runs.

### Summary

Your terminal environment is authenticated and linked to your Google Cloud project.
