# Why we're building the Render Pipeline how we are

## Capture Hardware Constraints

We *only* have access to the iPad Pro 3rd Gen (2021), with an additional Structure Sensor attachment. This is what is in our kit, and we need to design for it. Note other cameras/technologies as nice-to-haves, and tell me about them (we can redesign the kit later after initial pipeline prototype in place).

But I want to emphasize -- the goal of this pipeline is to reduce clinician friction as much as possible for a remote startup attempt to capture patient data. The whole point -- super easy for clinician/patient to take photos and send to me (dev) to toss in this pipeline and get a model. If we wanted to set up a whole photogrammatry station and harness to take perfect photos/scans, we would have started a different company (or I'd be building a different tool).  

The purose of this pipeline to take whatever we get and produce something. If the tech doesn't exist yet, or the math isn't there, tell me -- we'll invent our own. We didn't start a company to buy a tool off the shelf to solve a problem -- we're addressing a problem that has no tools. Dream goal solution -- encapsulate our fully functioning pipeline into an app such that the clinician can take photos and get the 3D model to review right there in the office, in one visit (and re-take if neccessary). If good, model is shipped to next stage (review by human, then off to Stratasys for 3D printing).

## Remote Clinic Flow & Tolerance For Imperfection

My dream scenario is to take photos from the remote clinic capture (we physically mail them a kit with camera), even if those photos are garbage and not quite perfect, and produce *something*. Once this pipeline is in place (even if it produces imperfect prints), we'll polish and perfect.  

(Note, when I say garbage, I don't mean blurry or bad... just not ideal, or not enough photos). If I could have the patient stand in a 360 booth and get the photos/scan, we'd have a different product -- but the company HyperReal is fully remote and attempting to eliminate any brick & mortar component from the business, deploying directly to clinicians at their clinic (using the clinician in clinic actually empowers the patient to pay for the prosthetic cover with insurance with special codes, which they can't do with other companies -- this is the key to funding and our competitive advantage).

---

## Polycam Strategy

I'll explore the Polycam approach. I'll work on that to get an initial test data set. When I was working on the prior iteration, we considered Polycam as the primary capture vehicle, but I never tested it because I didn't have the device/kit back (was with first patient). I then pivoted because I had a batch of patient data/capture without Polycam, and was hoping to produce something good from that.  

## Beyond Polycam and COLMAP

I do want to push back on "if Polycam can't do it, COLMAP can't either". That may be true. But if COLMAP can't do it, we need a different technology or we need to roll our own. This is the age of AI, so leveraging you, AI research frameworks (just ask and I'll send off Perplexity on massive deep dives for you and save the reports to `docs`) to empower me or other humans to push the frontiers of innovation and invent new tools/tech should be the new normal.  

As we develop and iterate and identify these pitfalls, surface them clearly in docs to roadmap this bumpy road so we can come back and design/build/invent the tool that *can*.