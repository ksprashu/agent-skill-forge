# 4-Panel Setup Comic Storyboard Templates (Optional Character Packs)

When an author configures an optional companion character pack (`node <skill-dir>/scripts/characters.cjs status` exits `0`, e.g. Companion A `"Pip"` as builder and Companion B `"Byte"` as architect), use the 4-panel storyboard beats below together with the resolved pack's `visual_prompt_descriptor` and reference sheets to generate cohesive setup comics. When no character pack is installed (`exit 1`), skip comic generation and use clean UI screenshots or diagrams.

## Comic 1: Activate Billing (Trial Credits)
**Slot Key:** `activate_billing` (`img/activate_billing_comic.png`)
**Layout:** 4-panel 2x2 grid.

- **Panel 1 (Top-Left):** **Incognito Mode.** Companion B next to an "Incognito" browser window icon. Caption: "Step 1: Open Incognito!"
- **Panel 2 (Top-Right):** **Gmail Sign-in.** Companion A pointing to a personal Gmail sign-in screen. Caption: "Step 2: Sign in with Personal Gmail."
- **Panel 3 (Bottom-Left):** **Access Credits.** Companion A pressing a glowing button reading "ACCESS CREDITS". Caption: "Step 3: Claim your credits!"
- **Panel 4 (Bottom-Right):** **Success.** Both companions celebrating in front of a green checkmark reading "Trial Activated!".

## Comic 2: Create Project
**Slot Key:** `create_project` (`img/create_project_comic.png`)
**Layout:** 4-panel 2x2 grid.

- **Panel 1 (Top-Left):** **Google Cloud Console.** Both companions facing a monitor displaying the Google Cloud Console. Caption: "Step 1: Open the Console."
- **Panel 2 (Top-Right):** **Project Name.** Companion A writing `my-awesome-app` into a project name input box. Caption: "Step 2: Name your project!"
- **Panel 3 (Bottom-Left):** **Billing Association.** Companion B selecting the "Trial Billing Account" badge from a dropdown menu. Caption: "Step 3: Link Trial Billing."
- **Panel 4 (Bottom-Right):** **Create Button.** Companion A clicking a blue "CREATE" button. Caption: "Step 4: Click CREATE!"

## Comic 3: Verify Billing Link
**Slot Key:** `verify_billing` (`img/verify_billing_comic.png`)
**Layout:** 4-panel 2x2 grid.

- **Panel 1 (Top-Left):** **Billing Overview.** Companion B inspecting a screen labelled "Billing Overview". Caption: "Step 1: Open Billing."
- **Panel 2 (Top-Right):** **The Link.** Companion A connecting the project icon to the Trial Billing badge. Caption: "Step 2: Confirm the link!"
- **Panel 3 (Bottom-Left):** **Trial Account Selection.** Companion B pointing to "TRIAL ACCOUNT" on the billing selector. Caption: "Step 3: Select Trial."
- **Panel 4 (Bottom-Right):** **Ready to Build.** Both companions giving a thumbs-up next to a green status indicator. Caption: "Ready to build!"

## Comic 4: Environment Setup
**Slot Key:** `environment_setup` (`img/environment_setup_comic.png`)
**Layout:** 4-panel 2x2 grid.

- **Panel 1 (Top-Left):** **The Choice.** Companion A pointing to a browser Cloud Shell icon while Companion B sits at a local laptop terminal. Caption: "Step 1: Pick your terminal!"
- **Panel 2 (Top-Right):** **Cloud Shell Activate.** Companion A clicking the top-right terminal icon in the Cloud Console. Caption: "Step 2: Activate Cloud Shell."
- **Panel 3 (Bottom-Left):** **Authorise.** Companion B approving the CLI authorisation prompt. Caption: "Step 3: Authorise access."
- **Panel 4 (Bottom-Right):** **Project Check.** Companion A verifying `gcloud config get-value project` in the terminal. Caption: "Step 4: Confirm Project ID!"
