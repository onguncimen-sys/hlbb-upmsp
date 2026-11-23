
using DelimitedFiles

function InputData(n::Int16, m::Int8)

    #----- Especify the location of the file in the respective folder

    LOC::String = "/code/Example/I_6_2_S_1-9_1.txt" 
    
    F = readdlm(LOC, skipblanks = true, skipstart = 2)

    #----- Input the matrix of processing times

    p = zeros(Int16, m, n)

    for i in 1:n 
        line = F[i,1:m*2]
        for j in eachindex(line)
            if j % 2 == 0
                mach::Int8 = j/2  
                p[mach,i] = line[j]
            end
        end
    end

    #----- Input the sequence dependent setup times
    
    S = Matrix{Int16}[]
    c::Int32 = n
    
    for i in 1:m
        if i == 1
            c += 3
        else
            c += n+1
        end

        MSDST = zeros(Int16, n, n) 
        count::Int32 = 1

        for j in c:c+n-1
            line = F[j,1:n]
            for k in eachindex(line)
                MSDST[count, k] = line[k]
            end
            count += 1
        end

        push!(S, MSDST)
    end
    
    return(p, S)
end