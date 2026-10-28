"""Task knowledge backed by local Sketchpad 5.06 trials, not guessed macros."""
from copy import deepcopy


WORKFLOWS = {
    "four_graph_delivery": {
        "verification": "four_saved_gsp_files_reopened_and_drag_verified_2026_10_28",
        "purpose": "Refine and verify native inverse-function rectangle and triangle diagrams.",
        "steps": [
            "List MDI documents and activate the exact handle and filename. Do not reopen a same-name document.",
            "Observe a fresh image after activation or scrolling. Scale coordinates independently for each dialog image.",
            "Clear selection at observed blank canvas; select only the intended object. Inspect enabled object-specific menu captions before editing.",
            "Keep native functions, intersections, feet and interiors. Hide raw centimetre measurements, not their dependencies. Label normalized coordinate area S.",
            "Set each selected native plot to 2000 continuous samples in Properties > Plot. Restrict the displayed interval to the needed branch while retaining the original function.",
            "Use distinct curve colours, pale fill, constrained edge segments and consistent point names. Hide a duplicate origin label, not the axis itself.",
            "Toolbox action buttons execute when clicked, including additive clicks. Select their group using an observed enclosing marquee; avoid canvas edges that autoscroll.",
            "Save to a new file, close the saved document, reopen it and verify the active filename. Drag the controlling point; inspect geometry and S; undo the drag to restore layout.",
        ],
        "verified_cases": {"same_sign_rectangle": 3, "same_sign_triangle": 1.5,
                           "opposite_sign_rectangle": 9, "opposite_sign_triangle": 4.5},
        "limits": ["Normal positive controller positions only; axis crossing and extreme positions are not verified.",
                   "Coefficients remain editable native functions; dedicated coefficient sliders are not implemented.",
                   "Do not reuse the trial's pixel locations on a different viewport or document."],
    },
    "toolbox_coordinates": {
        "verification": "ui_and_saved_native_objects_verified",
        "purpose": "Create finite, editable axes using toolbox 07.",
        "tool_path": ["07 新新坐标系", "新坐标系工具"],
        "preconditions": ["New or intentionally editable document", "Observed empty canvas location"],
        "steps": [
            "Select the exact tool path; confirm status asks to match point *.",
            "Click the desired origin once, then switch to the selection tool.",
            "Click observed blank canvas to clear selection; inspect finite axes and controls. Check conventional versus trigonometric scale mode before proceeding.",
        ],
        "native_result": "172 objects in the verified trial, including coordinate system and bounds.",
        "pitfalls": ["Popup navigation includes disabled rows and separators.",
                     "Do not click an existing object unless intentionally supplying it as origin."],
    },
    "bounded_inverse_function": {
        "verification": "saved_native_dependencies_verified_k6_additional_ui_trial_k3",
        "purpose": "Plot editable k/x clipped to the toolbox coordinate frame.",
        "tool_path": ["07 新新坐标系", "函数y=f(x)图像"],
        "preconditions": ["Verified toolbox 07 coordinate system exists", "No unintended selection"],
        "steps": [
            "Use Plot > New Function to open the native calculator.",
            "In the observed EMPTY calculator call sketchpad_enter_inverse_function(numerator=k).",
            "Observe the stacked fraction and the initial unbounded native curve.",
            "Clear selection by clicking observed blank canvas.",
            "Select the exact custom tool; confirm status asks to match function y=f(x).",
            "Click the observed native function formula once; inspect the bounded curve.",
            "Select ONLY the initial curve outside the frame and hide it using Display > Hide Function Plot.",
        ],
        "native_result": {"function": 173, "initial_plot": 174, "bounded_function": 175,
                          "bounded_plot": 176, "coordinate_system": 12,
                          "bounded_function_parents": [173, 46, 45, 144, 142],
                          "bounded_plot_parents": [175, 12]},
        "pitfalls": [
            "Tag 1204 lists candidate matching objects, NOT a verified mandatory click order.",
            "In this trial only the function was clicked; coordinate system and bounds matched automatically.",
            "Clear selection before selecting the original curve; otherwise both plots may be hidden.",
            "Multiple coordinate systems and negative k still need UI verification.",
        ],
    },
    "constrained_intersections": {
        "verification": "pending_ui_trial_in_toolbox_coordinates",
        "purpose": "Create actual constrained intersections and axis feet.",
        "steps": ["Select existing curves and use native intersection construction.",
                  "Construct parallel/perpendicular lines from actual points and axes, then intersect."],
        "pitfalls": ["Pixel locations identify objects; they must not substitute for geometry constraints."],
    },
    "dynamic_fill": {
        "verification": "pending_ui_trial",
        "purpose": "Fill rectangles or triangles whose vertices follow constrained points.",
        "steps": ["Use the polygon tool on the existing vertices in boundary order; double-click the last vertex.",
                  "Drag a controlling point and verify the fill follows."],
        "pitfalls": ["Do not paste an image as a replacement for editable geometry."],
    },
    "fraction_annotation": {
        "verification": "native_caption_subscript_and_stacked_fractions_saved_and_reopened_2026_10_28",
        "purpose": "Display correct stacked fractions in editable annotations.",
        "steps": ["Use the native calculator for function fractions.",
                  "Create an empty native caption with the text tool. Read sketchpad_list_builtin_tools and open the symbol panel only when checked is false.",
                  "Insert the subscript template FIRST, fill the base S, Tab to the subscript and fill it, then Right twice to exit.",
                  "For each stacked fraction insert the native fraction template, fill numerator, Tab to denominator, fill it, then Right twice to exit.",
                  "Use sketchpad_set_caption_size on selected native text; do not send font-size digits through the canvas input method.",
                  "Known short caption/template sequences may use sketchpad_batch with sketchpad_type_literal and sketchpad_key; inspect focus and panel state first.",
                  "Prefer sketchpad_fill_math_caption for the six inverse-function caption templates. Ensure the symbol panel once, then create an EMPTY caption. If status is blank after the drag, hover an observed blank canvas point outside the caption and read the live editing status before calling the tool. Do not click outside, which would end editing.",
                  "Reopen the saved GSP and inspect both the formula and native geometry. Symbolic captions are editable annotations, not dynamic coefficient bindings."],
    },
    "reference_angle_marks": {
        "verification": "native_marks_saved_reopened_and_controller_drag_verified_in_three_diagrams",
        "purpose": "Add native right-angle marks and finite auxiliary segments to toolbox-coordinate diagrams.",
        "steps": ["Use actual adjacent native segments at each angle vertex. Toolbox axes are function plots and cannot replace native segments in this operation.",
                  "For a new axis foot, construct native perpendicular lines, intersect them and replace their visible extensions with finite segments.",
                  "Choose an observed vertex and call sketchpad_add_angle_mark with offsets into the intended angle. The tool verifies the live angle-target status before dragging.",
                  "If the tool stops, refresh and inspect the vertex or missing adjacent segments. Never repeat a freehand marker drag.",
                  "Reopen and drag the controller; check marks, feet, auxiliary segments, fill and normalized area together."],
        "limits": ["Four individual native diagrams verified; a single native four-column layout is not verified.",
                   "Curve-side symbolic captions do not automatically reposition with the controller."]
    },
    "efficient_four_graph_refinement": {
        "verification": "formula_and_repeated_tool_selection_benchmarked_2026_10_28_full_four_graph_runtime_not_benchmarked",
        "purpose": "Reduce repeated tool discovery and model round trips while preserving native geometry quality.",
        "steps": [
            "Before drawing, make a per-diagram checklist: function definitions, toolbox axes, constrained intersections, finite guides, fill, point names, right angles, curve captions, area formula and final layout. Identify outstanding deliverables explicitly.",
            "Use the existing four_graph_delivery, reference_angle_marks and fraction_annotation recipes. Read only the relevant recipe; do not re-read a full manual or repeat installed-tool enumeration for verified operations.",
            "Activate the exact document once and observe. Use sketchpad_select_and_construct for each known constraint and sketchpad_fill_math_caption for native formulas. Avoid individual model requests for every Tab or text fragment.",
            "Ensure the symbol panel once using sketchpad_set_symbol_panel. Do not enumerate all toolbar controls or installed fonts for every caption. Recheck after a toolbar/layout change.",
            "Inspect images after each logical component and all context transitions. Use metadata-only refreshes inside already-validated bounded sequences; retain final image checks.",
            "After an unavailable construction or unrecognized target, inspect the selected object type and refresh once. If the same failure recurs, stop that attempt and report the missing precondition; do not repeat stale coordinates or experiment in a delivery document.",
            "Keep template, font and layout experiments in a separate scratch document. Complete code changes and tests before one service restart, then run the relevant live benchmark.",
            "Verify geometry by controller drag, native formula rendering and persistence. Report task wall time, request count, errors/retries and remaining reference mismatches separately from per-tool speed.",
        ],
        "limits": ["The measured speedups cover repeated tool selection and caption filling, not an entire four-diagram reconstruction.",
                   "First UI Automation discovery still takes seconds; a native single-page four-column template is pending."]
    },
}


def get_workflow(task=None):
    if task is None:
        return {"tasks": [{"task": key, "purpose": value["purpose"],
                           "verification": value["verification"]} for key, value in WORKFLOWS.items()]}
    if task not in WORKFLOWS:
        raise ValueError("Unknown task; call sketchpad_get_workflow without task to list tasks.")
    return {"task": task, **deepcopy(WORKFLOWS[task])}
