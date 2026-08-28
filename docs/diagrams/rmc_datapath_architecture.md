# RMC Datapath Architecture — Diagram

Visual summary of the datapath architecture defined in
[`docs/rmc_datapath_architecture.md`](../rmc_datapath_architecture.md); read that document for
the full explanation, sourcing, and OPEN items.

Source figures: `docs/sched_rebuild/fig/fig_06_datapath.py`, `fig_mcc_block.py`,
`fig_05_packer.py`.

```mermaid
flowchart TB
    L3["L3 / Rank Arb"] --> PACKER["Phase Packer"] --> COMMIT{{"CAS Commit\n{op, tag, sram_addr}"}}

    COMMIT -->|"WR"| WL
    COMMIT -->|"RD"| RL

    subgraph WDW[" "]
        WDSRAM[("WD_SRAM\nCIF-owned")]
    end

    subgraph MCCDP["MCC DATA PATH   ·   BL16 = 512b   ·   1:4 gear   ·   2 mc_clk / burst"]
        direction LR

        subgraph WRP["WRITE PATH"]
            direction TB
            WL["WL timing\ndepth = CWL"]
            SPLIT["Write Burst\nSplitter"]
            WTX["DFI TX\nwrite data"]
            WDONE["wr_done"]
            WL -. launch .-> SPLIT
            SPLIT --> WTX --> WDONE
        end

        subgraph RDP["READ PATH"]
            direction TB
            RL["RL timing\ndepth = CL"]
            RRX["DFI RX\nread data"]
            ACC["Read\nAccumulator"]
            RDONE["rd_done"]
            RRX --> ACC --> RDONE
            RL -. arms .-> ACC
        end
    end

    WDSRAM --> SPLIT

    subgraph RDW[" "]
        RDSRAM[("RD_SRAM\nCIF-owned")]
    end
    ACC --> RDSRAM

    DRAMW[("DRAM")]
    DRAMR[("DRAM")]
    WTX --> DRAMW
    DRAMR --> RRX

    COMP["Completion / Response"]
    WDONE --> COMP
    RDONE --> COMP
    COMP --> CIFOUT["-> CIF"]

    classDef sram fill:#e8e2f5,stroke:#7a5cb8,stroke-width:1.8px,color:#3a2a5c;
    classDef ext fill:#eef1f4,stroke:#607080,stroke-width:1.4px,color:#334;
    classDef commit fill:#fff3cd,stroke:#b8860b,stroke-width:1.8px,color:#5c4400;
    classDef wr fill:#e4f0ff,stroke:#2b6cb0,stroke-width:1.4px,color:#123a5e;
    classDef rd fill:#e6f7e9,stroke:#2f8a4e,stroke-width:1.4px,color:#164a29;
    classDef comp fill:#fdeedd,stroke:#c2701c,stroke-width:1.6px,color:#5a3510;
    classDef wrap fill:none,stroke:none;

    class WDSRAM,RDSRAM sram;
    class DRAMW,DRAMR,CIFOUT ext;
    class COMMIT commit;
    class WL,SPLIT,WTX,WDONE wr;
    class RL,RRX,ACC,RDONE rd;
    class COMP comp;
    class WDW,RDW wrap;
```
