## Introduction

Large language models (LMs) have demonstrated significant proficiency in zero-shot and few-shot reasoning, yet they remain constrained by inherent limitations, including factual hallucinations, lack of temporal awareness, and the inability to interface with external computational tools [Schick et al., 2023]. While previous research has attempted to mitigate these issues through tool-use frameworks, such as the self-supervised Toolformer [Schick et al., 2023] or interactive agents [Park et al., 2023], these systems often struggle with long-term coherence or the ability to chain tool executions effectively. We propose the SynapseAgent framework, a cognitive architecture that integrates self-supervised tool acquisition with recursive memory management to facilitate autonomous, long-horizon task execution.

## Method

The SynapseAgent framework is designed as a cognitive architecture that facilitates autonomous, long-horizon task execution through the tight integration of self-supervised tool acquisition and recursive memory management. The architecture is defined by the memory-object tuple $(O, R, P)$, where $O$ denotes the set of environmental observations, $R$ represents the set of reflective insights derived from past experiences, and $P$ denotes a set of hierarchical plans that guide agent behavior. This structure serves as the primary interface between the agent's perception and its decision-making modules.

The retrieval of information from this memory structure is governed by the scoring function $S = w_r \cdot \text{Recency}(m) + w_i \cdot \text{Importance}(m) + w_l \cdot \text{Relevance}(m, q)$, where $m$ is a specific memory record from the tuple $(O, R, P)$, $q$ is the current task query, and $w_r, w_i, w_l$ are learned weights that prioritize different dimensions of memory access. Recency is modeled as an exponential decay function, importance is assessed via an LLM-based scoring mechanism, and relevance is calculated through the cosine similarity of embedding vectors, consistent with the retrieval mechanisms explored in [Park et al., 2023].

The architectural flow is illustrated in Figure 1, which depicts the recursive interaction between the perception of environmental feedback and the internal planning state.

```tikz
\begin{figure}[h]
\centering
\begin{tikzpicture}[node distance=1.5cm, auto, font=\small]
    \node[draw, rectangle] (obs) {Observations (O)};
    \node[draw, rectangle, right=of obs] (ref) {Reflections (R)};
    \node[draw, rectangle, right=of ref] (plan) {Plans (P)};
    \node[draw, ellipse, below=of ref] (llm) {LLM Core};
    \node[draw, rectangle, left=of llm] (tools) {API Library};
    
    \draw[->] (obs) -- (llm);
    \draw[->] (ref) -- (llm);
    \draw[->] (plan) -- (llm);
    \draw[->] (llm) -- (tools);
    \draw[->] (tools) -- (obs);
    \draw[->, bend left] (llm) to (ref);
    \draw[->, bend left] (llm) to (plan);
\end{tikzpicture}
\caption{The SynapseAgent architecture, illustrating the recursive flow between the memory-object tuple (O, R, P) and the LLM-driven tool-use engine.}
\end{figure}
```

To address the limitations of non-chained tool use observed in [Schick et al., 2023], SynapseAgent implements a multi-stage tool-chaining algorithm. This process is structured as follows: (1) The agent decomposes the high-level task into a sequence of sub-goals stored in $P$; (2) The agent selects an appropriate tool from the API library based on the current sub-goal; (3) The tool is executed, and the resulting output is integrated into the observation set $O$; (4) The system updates the memory stream with the new observation; (5) The reflection module processes the outcome to generate a new reflective insight $R$, which is then used to refine subsequent plans in $P$. This recursive loop ensures that the agent can adapt its strategy based on the intermediate outputs of its tool-use actions, a capability absent in earlier models like the base Toolformer [Schick et al., 2023].

The training objective for SynapseAgent is formulated as maximizing the probability of correct tool-use sequences while simultaneously minimizing the perplexity of the model on future task-relevant tokens. This is achieved through a prompting-based training mode, where the model is provided with few-shot demonstrations of successful tool-use sequences. Unlike standard ReAct prompting [Yao et al., 2023], which relies on static reasoning traces, SynapseAgent employs a self-supervised filtering mechanism to determine the utility of API calls. Following the approach in [Schick et al., 2023], where the model (GPT-J, 6.7B) evaluates API utility by comparing cross-entropy loss with and without the tool, an API call is retained if it reduces the loss by a threshold $\tau_f$.

The computational complexity of the framework is dominated by the attention-based retrieval mechanism, which operates at $O(n^2)$ relative to the length of the memory stream, while memory storage scales linearly with the number of interactions. The cost of running the simulation is primarily driven by the frequency of API calls and the volume of LLM inference tokens, as noted in [Park et al., 2023], where simulations using gpt-3.5-turbo incurred significant token costs. By utilizing the $(O, R, P)$ tuple, SynapseAgent aims to mitigate the high computational costs identified in [Park et al., 2023] by enabling more efficient, targeted retrieval rather than exhaustive memory scanning. We hypothesize that the recursive nature of the reflection module will significantly reduce the frequency of redundant API calls by allowing the agent to synthesize past tool-use outcomes into abstract knowledge, thereby preventing the repetition of unsuccessful search patterns.

## Evaluation Plan

We propose to evaluate the SynapseAgent framework across two primary dimensions: task-specific performance and long-term behavioral coherence. 

First, we plan to evaluate tool-use efficacy on the benchmarks established in [Schick et al., 2023], specifically the LAMA dataset for factual lookup and math benchmarks such as ASDiv, SVAMP, and MAWPS. We aim to compare our chained-execution approach against the baseline Toolformer (6.7B parameters, zero-shot), which achieved 53.5 accuracy on T-REx and 44.0 on MAWPS [Schick et al., 2023, Table 3, 4]. We hypothesize that the ability to chain tools will yield performance gains in complex multi-step reasoning tasks where the base Toolformer is currently limited.

Second, we plan to conduct a long-horizon simulation in a sandbox environment, modeled after the Smallville simulation in [Park et al., 2023]. We will measure the agents' ability to maintain consistent social behaviors and information diffusion over an extended duration. We plan to utilize the TrueSkill rating system, as employed in [Park et al., 2023, Figure 8], to assess the believability of agent interactions, comparing our $(O, R, P)$ architecture against the ablated versions (e.g., no reflection, no planning) used in the original study.

## Discussion

The integration of these components allows SynapseAgent to operate in a self-supervised manner, learning to navigate complex environments by treating tool-use as a language modeling problem. By grounding the agent's reasoning in persistent, structured memory, we expect the framework to maintain higher coherence in long-duration simulations compared to architectures that treat reasoning and memory as disconnected processes. The evaluation of this architecture will focus on verifying whether the synergy between self-supervised tool acquisition and reflective memory management provides a scalable path toward autonomous, long-horizon task completion. We acknowledge that, similar to [Park et al., 2023], our framework remains susceptible to risks such as hallucination and memory embellishment, which we plan to address in future iterations by refining the importance and relevance weighting functions.