<!--
Copyright 2026 Google LLC.
SPDX-License-Identifier: Apache-2.0
-->

## Preparing your Workspace (Environment Setup)

Duration: 5:00

You need a place to run your code! You have two great choices, and our pets will help you decide:

<img src="img/environment_setup_comic.png" alt="Malti and Raggy's guide to choosing an environment" width="624.00" />

### **Option 1: Google Cloud Shell (Malti's Favorite! ☁️)**

Cloud Shell is a browser-based terminal that comes pre-installed with everything you need: [Node.js](https://nodejs.org/), [gcloud CLI](https://cloud.google.com/sdk/gcloud), and [git](https://git-scm.com/). It’s fast, free, and works anywhere!

#### **1. Activate Cloud Shell**

Click the **'Activate Cloud Shell' icon** in the top-right of your Google Cloud Console.

Cloud Shell will take a moment to provision. If prompted, click **Authorize** so it can talk to Google Cloud for you. 

Wait until you see the prompt: `user @cloudshell:~ $`.

#### **2. Verify Your Project**

Malti wants to make sure we're in the right place. Run this:

```bash
gcloud config get-value project
```

If it doesn't show your project ID, set it manually:

```bash
gcloud config set project <YOUR-PROJECT-ID>
```

---

### **Option 2: Local Terminal (Raggy's Choice! 💻)**

If you prefer your own setup (iTerm, VS Code Terminal, etc.), you'll need a few things installed first.

#### **1. Install Prerequisites**

Make sure you have:
*   [Node.js v20+](https://nodejs.org/)
*   [Google Cloud SDK (gcloud CLI)](https://cloud.google.com/sdk/docs/install)

#### **2. Login and Configure**

Sign in to your account:
```bash
# Copyright 2026 Google LLC.
# SPDX-License-Identifier: Apache-2.0

gcloud auth login
```

Set your project:

```bash
# Copyright 2026 Google LLC.
# SPDX-License-Identifier: Apache-2.0

gcloud config set project <YOUR-PROJECT-ID>
```

Set up application credentials (this helps your code talk to Google APIs):

```bash
# Copyright 2026 Google LLC.
# SPDX-License-Identifier: Apache-2.0

gcloud auth application-default login
```

### Summary

Workspace ready? Awesome! 

Next, let's meet our new best friend in **Meeting Gemini CLI**.
